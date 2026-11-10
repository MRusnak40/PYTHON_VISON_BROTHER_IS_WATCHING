# POSTUP ROZPOZNÁVÁNÍ JEDNOHO SNÍMKU.
# Spojuje detektor, tracker a úložiště osob, ale sama nečte kameru.
# Neznámému tracku potvrzuje identitu; známému vybírá vhodné další vzorky.

"""Život identity: detekce → tracking → potvrzení osoby → zlepšování vzorků."""

from time import perf_counter
from typing import NamedTuple

from .profiles import cosine_distance
from .tracking import FaceTracker


class PipelineResult(NamedTuple):
    """Jediný výsledek snímku; lze číst .labels/.events i rozbalit jako původní dvojici."""

    labels: list  # [(box, text)], box = (x, y, šířka, výška) v původním obrazu.
    events: list  # Slovníky změn identity/vzorků: status, person_id, track_id, případně distance.


# Řídí pořadí kroků a počítá statistiky jejich náročnosti.
class VisionPipeline:
    # ==================== STAV A MĚŘENÍ ====================
    # Převezme modely, úložiště a nastavení; vytvoří dočasný tracker.
    def __init__(self, processor, store, settings):
        self.processor = processor  # FaceProcessor: detekce, kvalita a embeddingy.
        self.store = store  # ProfileStore: galerie a zápis vybraných vzorků.
        self.settings = settings  # Settings: intervaly a prahy rozhodování.
        self.tracker = FaceTracker(settings)  # Tracky aktuálního běhu, nikoli trvalé osoby.
        # Kumulativní počítadla; *_seconds jsou doby výpočtu, ostatní počty volání.
        self.stats = {"frames": 0, "embeddings": 0, "matches": 0,
                      "embedding_seconds": 0.0, "detection_seconds": 0.0}

    # Spočítá embedding a změří délku volání; finally zaznamená pokus i při chybě.
    def _embed(self, observation):
        """Vrátí FaceCandidate nebo None; současně započítá dobu výpočtu embeddingu."""
        started = perf_counter()  # Přesné stopky tohoto jediného volání.
        try:
            return self.processor.embed(observation)
        finally:
            self.stats["embeddings"] += 1
            self.stats["embedding_seconds"] += perf_counter() - started

    # ==================== NEZNÁMÝ TRACK: POTVRZENÍ IDENTITY ====================
    def _resolve(self, track, observation, now, timestamp):
        """Vrátí událost nebo None, pokud identita zatím není potvrzená.

        track = dočasný stav; observation = výřez jedné detekce;
        now = datum UTC do profilu; timestamp = monotonic sekundy pro intervaly.
        """
        # Pokud ještě neuplynul interval, drahý výpočet přeskočíme.
        if timestamp < track.next_recognition:
            return None
        track.next_recognition = timestamp + self.settings.recognition_interval
        quality = self.processor.evaluate(observation)  # Slovník usable/score/view/fingerprint.
        # Identitu nerozhodujeme z malého, rozmazaného nebo jinak nekvalitního výřezu.
        if not quality["usable"] or quality["score"] < self.settings.identity_quality:
            return None
        candidate = self._embed(observation)  # Výřez + kvalita + číselný vektor identity.
        if candidate is None:
            return None
        self.stats["matches"] += 1
        # Porovnáme vektor s uloženými profily; menší distance znamená podobnější.
        index, distance, ambiguous = self.store.match(candidate.embedding)
        # index = pozice profilu nebo None; distance = cosine distance;
        # ambiguous = dva profily vyšly příliš podobně, nikoli pravděpodobnost.
        track.ambiguous_identity = ambiguous
        # Dvě osoby vyšly příliš podobně: počkáme na lepší podklad a nic nezakládáme.
        if ambiguous:
            track.evidence.clear()
            track.match_person, track.match_votes = None, 0
            return None
        # Existující profil potvrdíme až po opakované jasné shodě se stejným ID.
        if index is not None:
            person_id = self.store.profiles[index]["person_id"]  # Trvalé lokální ID, ne track_id.
            return self._confirm_existing(track, candidate, person_id, distance, now)

        return self._confirm_new(track, candidate, now)

    def _confirm_existing(self, track, candidate, person_id, distance, now):
        """Sbírá hlasy pro existující profil; vrátí událost bound, nebo None."""
        track.evidence.clear()
        track.match_votes = track.match_votes + 1 if track.match_person == person_id else 1
        track.match_person = person_id
        if track.match_votes < self.settings.match_observations:
            return None
        # DŮLEŽITÁ KONTROLA: dva současné tracky nesmějí získat stejnou osobu.
        # other je jiný aktivní Track, nikoli další vzorek galerie.
        if any(other is not track and other.person_id == person_id
               for other in self.tracker.tracks.values()):
            return None
        track.person_id = person_id
        self.store.update_person(person_id, candidate, now)
        return {"status": "bound", "person_id": person_id, "distance": distance}

    def _confirm_new(self, track, candidate, now):
        """Sbírá konzistentní embeddingy; vrátí událost z observe(), nebo None."""
        track.match_person, track.match_votes = None, 0
        # Když v galerii není shoda, sbíráme důkazy pro novou osobu.
        # Nový embedding musí odpovídat předchozím embeddingům stejného tracku.
        if any(cosine_distance(candidate.embedding, previous) > self.settings.match_distance
               for previous in track.evidence):  # previous = starší embedding téhož tracku.
            track.evidence.clear()
        track.evidence.append(candidate.embedding)
        # Jedna fotka nestačí; vyžadujeme předepsaný počet konzistentních důkazů.
        if len(track.evidence) < self.settings.identity_observations:
            return None
        self.stats["matches"] += 1
        # Znovu ověříme galerii; jiný track mohl mezitím podobný profil právě založit.
        result = self.store.observe(candidate, now)  # Slovník status/person_id a údajů o zápisu.
        if result.get("person_id"):
            track.person_id = result["person_id"]
            track.evidence.clear()
        return result

    # ==================== ZNÁMÝ TRACK: ZLEPŠOVÁNÍ VZORKŮ ====================

    def _improve_known(self, track, observation, now, timestamp):
        """Aktualizuje známou osobu; vrátí událost nebo None, galerii neprohledává."""
        self.store.touch(track.person_id, now)
        if timestamp < track.next_quality:
            return None
        track.next_quality = timestamp + self.settings.quality_interval
        quality = self.processor.evaluate(observation)  # Levné posouzení bez embeddingu.
        if not self.store.wants_sample(track.person_id, quality, now):
            return None
        candidate = self._embed(observation)  # Drahý výpočet až pro užitečný vzorek.
        if candidate is None:
            return None
        return self.store.update_person(track.person_id, candidate, now)

    # ==================== JEDEN SNÍMEK OD WORKERU ====================

    def process(self, frame, now, timestamp) -> PipelineResult:
        """BGR snímek + datum UTC + monotonic čas → jeden PipelineResult."""
        started = perf_counter()  # Stopky aktuální detekce, nikoli čas pozorování.
        # Nejdřív hledáme obličeje; zatím nepočítáme embedding každého z nich.
        observations = list(self.processor.detect(frame))  # FaceObservation pro každý nalezený obličej.
        self.stats["detection_seconds"] += perf_counter() - started
        self.stats["frames"] += 1
        labels = []  # Obdélníky a texty určené pouze náhledu.
        events = []  # Změny určené výpisu v terminálu.
        # DŮLEŽITÁ SMYČKA D: jeden průchod pro každý viditelný přiřazený obličej.
        # track nese historii; observation obsahuje výřez právě z tohoto snímku.
        for track, observation in self.tracker.update(observations, timestamp):
            result = None  # Událost změny profilu/identity, nebo žádná změna.
            if track.person_id is None:
                result = self._resolve(track, observation, now, timestamp)
            else:
                result = self._improve_known(track, observation, now, timestamp)
            if result is not None:
                result["track_id"] = track.track_id
                events.append(result)
            name = track.person_id or ("nejista shoda" if track.ambiguous_identity else "cekam na identitu")
            # name je popisek; čekající track ještě nemusí mít uložený profil.
            labels.append((track.box, f"T{track.track_id} {name}"))
        # Změny časů zapisujeme v intervalech, nikoli při každé detekci.
        self.store.flush(now)
        return PipelineResult(labels, events)
