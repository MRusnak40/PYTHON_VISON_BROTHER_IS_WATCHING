# MÍSTNÍ PROFILY OSOB A JEJICH FOTOGRAFIE.
# JSON obsahuje ID, časy, metadata a embeddingy; JPEG soubory obsahují vybrané výřezy.
# Úložiště je pro jeden proces EDGE, bez centrální databáze a synchronizace.

"""Lokální matching osob a omezená sada průběžně zlepšovaných vzorků.

JSON spravuje jeden proces aplikace. Nový obrázek se zapisuje před JSON;
nahrazený obrázek se odstraní až po úspěšném uložení nového dokumentu.
"""

import copy
import json
import re
from datetime import datetime
from pathlib import Path
from typing import NamedTuple
from uuid import uuid4

import cv2
import numpy as np


# Chyba uložených dat; vadný JSON se nepřepíše prázdným.
class ProfileDataError(ValueError):
    pass


# Tři hlavní pohledy mají vyhrazená místa, aby je nezabraly všechny fotky z jedné strany.
PRIMARY_VIEWS = ("left", "front", "right")


class MatchResult(NamedTuple):
    """Jeden výsledek hledání v galerii; lze rozbalit jako původní trojici."""

    index: int | None  # Pozice v profiles, nikoli person_id; None = žádná přijatá shoda.
    distance: float | None  # Cosine distance nejlepší shody, menší = podobnější.
    ambiguous: bool  # Dvě osoby vyšly příliš podobně; takovou shodu nepotvrzujeme.


# Vybere nejlepší vzorek každého hlavního pohledu; vrátí jejich indexy a indexy doplňků.
def sample_roles(samples):
    """Seznam vzorků → dvojice (mapa hlavních pohledů na indexy, indexy doplňků)."""
    primary = {}  # Např. {"front": 0, "left": 2}; hodnoty jsou pozice ve samples.
    # DŮLEŽITÁ SMYČKA: vybere nejlepší vzorek pro každý ze tří hlavních pohledů.
    for index, sample in enumerate(samples):
        view = sample["quality"]["view"]  # Heuristický pohled left/front/right/unknown.
        if view in PRIMARY_VIEWS:
            previous = primary.get(view)  # Index dosud nejlepšího vzorku tohoto pohledu.
            if previous is None or sample["quality"]["score"] > samples[previous]["quality"]["score"]:
                primary[view] = index
    extras = [index for index in range(len(samples)) if index not in primary.values()]
    # extras jsou indexy zbývajících vzorků; hlavní pohledy se nesmějí vytlačit doplňky.
    return primary, extras


# Zapíše do vzorků role left/front/right nebo extra.
def assign_sample_roles(samples):
    """Upraví role uvnitř předaných vzorků; vrací None."""
    primary, _ = sample_roles(samples)
    for sample in samples:
        sample["role"] = "extra"
    for view, index in primary.items():
        samples[index]["role"] = view


# Porovná směry embeddingů. Menší vzdálenost znamená větší podobnost.
# Nejde o procento shody ani pravděpodobnost stejné osoby.
def cosine_distance(first, second):
    """Dva nenulové embeddingy → jedno číslo 0 až 2; nejde o pravděpodobnost."""
    # NumPy pole umožní výpočet přes skalární součin a délky vektorů.
    a, b = np.asarray(first, dtype=float), np.asarray(second, dtype=float)
    return float(np.clip(1 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)), 0, 2))


# Správce profilů v paměti, jejich porovnávání a ukládání na disk.
class ProfileStore:
    # ==================== NAČTENÍ A VALIDACE ====================
    # Načte data a vytvoří mapu person_id → pozice v seznamu profilů.
    def __init__(self, settings):
        self.settings = settings  # Settings: model, velikost vektoru, limity vzorků a zápisu.
        self.root = Path(settings.data_dir).resolve()  # Kořen všech místních dat EDGE.
        self.path = self.root / "storage" / "profiles.json"  # Centrální JSON tohoto procesu.
        self.missing_images = 0  # Počet chybějících JPEG zjištěný při načítání.
        self.data = self._load()  # Celý dokument {"profiles": [...]} v paměti.
        self.dirty = False  # Příznak neuložené změny časů pozorování.
        self.last_flush = None  # UTC datetime posledního zápisu, nebo None před prvním.
        # indexes: person_id → pozice profilu v self.profiles; zrychluje známé tracky.
        self.indexes = {profile["person_id"]: index for index, profile in enumerate(self.profiles)}
        if self.missing_images:
            print(f"Chybi {self.missing_images} fotek profilu; embeddingy zustavaji pouzitelne. "
                  "Chybejici vzorky se obnovi pri vhodnem pozorovani.", flush=True)

    # @property umožní číst store.profiles jako atribut místo volání profiles().
    @property
    def profiles(self):
        """Vrátí seznam profilů uvnitř aktuální verze dokumentu self.data."""
        return self.data["profiles"]

    # Načte JSON a ověří strukturu, model, časová pásma, cesty a embeddingy.
    def _load(self):
        """Vrátí ověřený dokument; neplatný JSON odmítne bez přepsání souboru."""
        # Chybějící či prázdný JSON znamená první start bez uložených osob.
        if not self.path.exists() or not self.path.read_text(encoding="utf-8-sig").strip():
            return {"profiles": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))  # Načtený dokument.
            if not isinstance(data, dict) or not isinstance(data.get("profiles"), list):
                raise ValueError
            seen = set()  # ID již ověřených profilů; odhaluje duplicity v JSON.
            # DŮLEŽITÁ SMYČKA: ověřit každý profil před spuštěním zpracování kamery.
            for profile in data["profiles"]:
                person_id = profile["person_id"]  # Trvalé místní ID typu person-0001.
                if not re.fullmatch(r"person-\d{4,}", person_id) or person_id in seen:
                    raise ValueError
                seen.add(person_id)
                self._validate_profile(profile)
            return data
        except (ValueError, KeyError, TypeError, OverflowError):
            raise ProfileDataError(
                "profiles.json je poskozeny nebo ma neplatne schema/model. "
                "Soubor zustal zachovan; nejdrive jej zkontroluj."
            ) from None

    def _validate_profile(self, profile) -> None:
        """Ověří metadata a vzorky jednoho profilu; doplní role, vrací None."""
        # Embeddingy různých modelů/normalizací nelze přímo porovnávat.
        if profile["embedding_model"] != self.settings.model_name:
            raise ValueError
        if profile["embedding_normalization"] != "base":
            raise ValueError
        samples = profile["face_samples"]  # 1 až max_samples vybraných vzorků jedné osoby.
        if not isinstance(samples, list) or not 1 <= len(samples) <= self.settings.max_samples:
            raise ValueError
        if any(datetime.fromisoformat(profile[key]).tzinfo is None
               for key in ("first_seen", "last_seen")):
            raise ValueError
        for sample in samples:
            self._validate_sample(sample, profile["person_id"])
        if profile["representative_image"] not in [sample["path"] for sample in samples]:
            raise ValueError
        assign_sample_roles(samples)  # Starším datům doplníme role bez odstraňování vzorků.

    def _validate_sample(self, sample, person_id) -> None:
        """Ověří jeden uložený vzorek; chybějící JPEG pouze započítá, vrací None."""
        file = self._sample_path(sample["path"], person_id)  # Ověřená absolutní cesta k JPEG.
        if not file.is_file():
            self.missing_images += 1  # Uložený embedding dál udržuje identitu použitelnou.
        vector = np.asarray(sample["embedding"], dtype=float)  # Vektor pro kontrolu tvaru/čísel.
        if (vector.shape != (self.settings.embedding_size,)
                or not np.isfinite(vector).all() or np.linalg.norm(vector) == 0):
            raise ValueError
        quality = sample["quality"]  # Persistované score, view, fingerprint a další metadata.
        if not 0 <= quality["score"] <= 1:
            raise ValueError
        if quality["view"] not in ("unknown", "front", "left", "right"):
            raise ValueError
        if not re.fullmatch(r"[0-9a-f]{16}", quality["fingerprint"]):
            raise ValueError
        if datetime.fromisoformat(sample["captured_at"]).tzinfo is None:
            raise ValueError

    # Převede relativní cestu na úplnou a ověří složku konkrétní osoby.
    def _sample_path(self, relative, person_id):
        """Relativní cesta a ID → ověřená absolutní Path uvnitř složky osoby."""
        path = (self.root / relative).resolve()  # Cílový soubor po odstranění ../ apod.
        directory = (self.root / "profiles" / person_id).resolve()  # Jediný povolený rodič.
        # Odmítneme cesty jako ../outside.jpg, které míří mimo určenou složku.
        if path.parent != directory or not directory.is_relative_to(self.root / "profiles"):
            raise ValueError("Neplatna cesta ke vzorku.")
        return path

    # Vybere místní ID person-0001 atd.; rezervuje i existující složky.
    # Tato čísla zatím nejsou globálně jedinečná mezi více EDGE zařízeními.
    def _next_id(self):
        """Vrátí dosud nepoužité místní person-ID, včetně rezervací složkami na disku."""
        numbers = [int(profile["person_id"].split("-")[1]) for profile in self.profiles]
        # numbers jsou číselné koncovky již použitých ID.
        directory = self.root / "profiles"  # Zde mohou být i složky dosud nezapsané do JSON.
        if directory.exists():
            numbers += [int(path.name.split("-")[1]) for path in directory.iterdir()
                        if re.fullmatch(r"person-\d{4,}", path.name)]
        return f"person-{max(numbers, default=0) + 1:04d}"

    # Každou osobu porovná přes její nejbližší vzorek a vyhodnotí nejlepší dvě osoby.
    # Vrací index profilu, vzdálenost a nejednoznačnost; data nemění.
    # ==================== MATCHING A VÝBĚR VZORKU ====================

    def match(self, embedding) -> MatchResult:
        """Embedding → jeden MatchResult; nezapisuje data ani nepotvrzuje track."""
        # Každou osobu zastupuje nejpodobnější vzorek; osoby seřadíme od nejnižší vzdálenosti.
        scores = sorted(
            (min(cosine_distance(embedding, sample["embedding"])
                 for sample in profile["face_samples"]), index)
            for index, profile in enumerate(self.profiles)
        )
        # scores = [(nejmenší distance ke vzorku osoby, index osoby)], vzestupně.
        if not scores or scores[0][0] > self.settings.match_distance:
            return MatchResult(None, None, False)
        distance, index = scores[0]
        # Pokud druhá osoba vyjde skoro stejně dobře, výsledek není dost jednoznačný.
        ambiguous = len(scores) > 1 and scores[1][0] - distance < self.settings.match_margin
        return MatchResult(index, distance, ambiguous)

    # Vrátí místo pro fotku: index pro nahrazení, délku seznamu pro přidání,
    # nebo None, když novou fotku nechceme ukládat.
    def _replacement(self, samples, quality, now):
        """Vzorky + nová kvalita + UTC čas → index nahrazení/přidání, nebo None."""
        if not samples:
            return 0
        # Hlídáme časový odstup mezi uloženými fotkami jedné osoby.
        latest = max(datetime.fromisoformat(sample["captured_at"]) for sample in samples)
        # latest je datum poslední uložené fotky, ne posledního detekovaného snímku.
        if (now - latest).total_seconds() < self.settings.sample_interval:
            return None
        # Chybějící soubor stejného pohledu může vhodná nová fotka obnovit.
        missing_view = [i for i, sample in enumerate(samples)
                        if sample["quality"]["view"] == quality["view"]
                        and not (self.root / sample["path"]).is_file()]
        if missing_view:
            return min(missing_view, key=lambda i: samples[i]["quality"]["score"])
        primary, extras = sample_roles(samples)  # Mapa hlavních pohledů a indexy doplňků.
        view = quality["view"]  # Pohled nového výřezu; unknown neslouží jako hlavní pohled.
        if view in PRIMARY_VIEWS:
            # Chybějící hlavní pohled má přednost před doplňky i s vyšším skóre.
            if view not in primary:
                if len(samples) < self.settings.max_samples:
                    return len(samples)
                return min(extras, key=lambda i: samples[i]["quality"]["score"]) if extras else None
            index = primary[view]
            if quality["score"] >= samples[index]["quality"]["score"] + self.settings.quality_improvement:
                return index

        return self._extra_replacement(samples, quality, extras)

    def _extra_replacement(self, samples, quality, extras):
        """Vybere místo pro doplňkový vzorek; vrátí jeden index, nebo None."""
        # XOR (^) označí rozdílné bity otisků, bit_count je spočítá.
        # Málo rozdílů znamená podobné fotky téhož pohledu.
        near_duplicates = [
            index for index, sample in enumerate(samples)
            if sample["quality"]["view"] == quality["view"]
            and (int(sample["quality"]["fingerprint"], 16)
                 ^ int(quality["fingerprint"], 16)).bit_count() <= 6
        ]
        # near_duplicates = indexy vizuálně blízkých vzorků stejného pohledu.
        if near_duplicates:
            duplicate_extras = [i for i in near_duplicates if i in extras]  # Jen nahraditelné doplňky.
            if not duplicate_extras:
                return None
            index = min(duplicate_extras, key=lambda i: samples[i]["quality"]["score"])
        elif len(extras) < self.settings.extra_samples and len(samples) < self.settings.max_samples:
            return len(samples)
        elif extras:
            index = min(extras, key=lambda i: samples[i]["quality"]["score"])
        else:
            return None
        if quality["score"] >= samples[index]["quality"]["score"] + self.settings.quality_improvement:
            return index
        return None

    # ==================== POZOROVÁNÍ A ZMĚNY PROFILU ====================

    # Najde nebo vytvoří osobu z kandidáta.
    # Živá pipeline sem smí dojít až po nasbírání důkazů identity.
    def observe(self, candidate, now):
        """FaceCandidate + UTC čas → událost; živá pipeline předem potvrzuje důkazy tracku."""
        if not candidate.quality["usable"]:
            return {"status": "poor_quality"}
        index, distance, ambiguous = self.match(candidate.embedding)
        if ambiguous:
            return {"status": "ambiguous", "distance": distance}
        return self._save_observation(candidate, now, index, distance)

    # Změní poslední pozorování v paměti a označí data pro budoucí zápis.
    def touch(self, person_id, now):
        """Nastaví last_seen známého profilu v paměti; vrací None."""
        self.profiles[self.indexes[person_id]]["last_seen"] = now.isoformat()
        # Data v paměti obsahují dosud neuloženou změnu.
        self.dirty = True

    # Levný předvýběr před embeddingem: lze vzorek této kvality a pohledu uložit?
    def wants_sample(self, person_id, quality, now):
        """Vrátí bool: má tato osoba místo pro tento užitečný vzorek právě teď?"""
        return quality["usable"] and self._replacement(
            self.profiles[self.indexes[person_id]]["face_samples"], quality, now,
        ) is not None

    # Aktualizuje potvrzenou osobu bez prohledávání galerie a zakládání další osoby.
    def update_person(self, person_id, candidate, now):
        """Vrátí událost aktualizace známého ID; nevyhledává ani nezakládá jinou osobu."""
        return self._save_observation(candidate, now, self.indexes[person_id], None)

    # Uloží vybranou fotku a změněný profil.
    # Starou fotku odstraní až po úspěšném uložení nové verze dat.
    def _save_observation(self, candidate, now, index, distance):
        """Připraví profil/vzorek a řídí jejich uložení; vrátí jeden slovník události."""
        if not candidate.quality["usable"]:
            return {"status": "poor_quality"}
        vector = np.asarray(candidate.embedding, dtype=float)  # Kontrola vektoru před zápisem.
        if (vector.shape != (self.settings.embedding_size,) or not np.isfinite(vector).all()
                or np.linalg.norm(vector) == 0):
            raise ValueError("Neplatny embedding.")
        # index ukazuje na existující profil; None znamená přípravu nové osoby.
        is_new = index is None  # True = nový profil, False = aktualizace existujícího.
        profile = self._prepare_profile(index, now)  # Pracovní kopie oddělená od uložených vzorků.

        samples = profile["face_samples"]  # Pracovní seznam vybraných fotografií a embeddingů.
        # Může vyjít None: identitu známe, ale další fotka by nebyla užitečná.
        slot = self._replacement(samples, candidate.quality, now)
        result = {"person_id": profile["person_id"], "distance": distance, "status": "matched"}
        # result je jediný výstup; matched může znamenat, že není potřeba ukládat další JPEG.
        if slot is None:
            return result

        directory = self.root / "profiles" / profile["person_id"]  # Složka vybrané osoby.
        # Složka osoby vznikne při ukládání; již existující složka nevadí.
        directory.mkdir(parents=True, exist_ok=True)
        # Unikátní název chrání původní fotku při selhání zápisu nového JSON.
        relative = f"profiles/{profile['person_id']}/face_{candidate.quality['view']}_{uuid4().hex}.jpg"
        file = self._sample_path(relative, profile["person_id"])  # Absolutní cesta nové fotografie.
        # Starou cestu si necháme pro odstranění až po úspěšném uložení náhrady.
        previous = samples[slot]["path"] if slot < len(samples) else None
        entry = {"path": relative, "captured_at": now.isoformat(),
                 "quality": candidate.quality.copy(), "embedding": candidate.embedding}
        if previous is None:
            samples.append(entry)
        else:
            samples[slot] = entry
        assign_sample_roles(samples)
        available = [sample for sample in samples
                     if sample is entry or (self.root / sample["path"]).is_file()]
        # available vylučuje chybějící staré JPEG; entry je právě připravovaný nový vzorek.
        # Hlavním obrázkem profilu je nejkvalitnější dostupná fotka.
        profile["representative_image"] = max(available, key=lambda sample: sample["quality"]["score"])["path"]
        self._commit_profile(profile, index, candidate.crop, file, now)
        # Starou fotku odstraníme až nyní, kdy nový JSON odkazuje na její náhradu.
        self._remove_replaced_sample(previous, profile["person_id"])
        result["status"] = "created" if is_new else "sample_replaced" if previous else "sample_added"
        result["quality"] = candidate.quality["score"]
        result["sample_role"] = entry["role"]
        return result

    def _prepare_profile(self, index, now) -> dict:
        """Vrátí nový nebo zkopírovaný profil; známému ID označí změnu last_seen."""
        if index is None:
            return {
                "person_id": self._next_id(), "first_seen": now.isoformat(),
                "last_seen": now.isoformat(), "embedding_model": self.settings.model_name,
                "embedding_normalization": "base", "face_samples": [],
            }
        self.profiles[index]["last_seen"] = now.isoformat()
        self.dirty = True
        return copy.deepcopy(self.profiles[index])

    # ==================== ZÁPIS NA DISK ====================

    def _commit_profile(self, profile, index, crop, file, now) -> None:
        """Zapíše pracovní profil a teprve potom přijme novou verzi do paměti; návrat None."""
        updated = copy.deepcopy(self.data)  # Celý budoucí JSON oddělený od aktuální verze.
        if index is None:
            updated["profiles"].append(profile)
        else:
            updated["profiles"][index] = profile
        self._write_sample(crop, file, updated)
        self.data = updated
        self.indexes[profile["person_id"]] = len(self.profiles) - 1 if index is None else index
        self.dirty = False
        self.last_flush = now

    def _remove_replaced_sample(self, previous, person_id) -> None:
        """Odstraní původní již nepoužívaný JPEG, pokud existoval; vrací None."""
        if previous:
            try:
                self._sample_path(previous, person_id).unlink(missing_ok=True)
            except OSError:
                print("Stary nepouzivany vzorek se nepodarilo odstranit.")

    def _write_sample(self, crop, file, updated) -> None:
        """Zapíše nový JPEG a potom JSON; při selhání uklidí nový JPEG, vrací None."""
        try:
            encoded, image = cv2.imencode(".jpg", crop)  # Úspěch převodu a pole JPEG bajtů.
            if not encoded:
                raise OSError("Vzorek nelze zapsat.")
            file.write_bytes(image.tobytes())
            self._write(updated)
        except Exception:
            file.unlink(missing_ok=True)
            raise

    # Zapíše celý JSON do dočasného souboru a jím nahradí původní.
    # Tím omezuje riziko ponechání napůl přepsaného původního souboru.
    def _write(self, data):
        """Dokument → zápis přes dočasný soubor a nahrazení původního; vrací None."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".profiles-{uuid4().hex}.tmp")  # Sousední dočasný JSON.
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                                 encoding="utf-8")
            # Hotovým souborem nahradíme původní místo průběžného přepisování jeho obsahu.
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    # Uloží změněné časy po uplynutí intervalu; force=True interval přeskočí.
    def flush(self, now, force=False):
        """Zapíše změněné časy po intervalu; force interval přeskočí, návrat None."""
        if self.dirty and (force or self.last_flush is None
                           or (now - self.last_flush).total_seconds() >= self.settings.flush_interval):
            self._write(self.data)
            self.dirty = False
            self.last_flush = now
