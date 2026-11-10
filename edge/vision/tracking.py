# DOČASNÉ SLEDOVÁNÍ OBLIČEJŮ MEZI SNÍMKY.
# Track propojuje rámečky podle polohy; person_id připojí až rozpoznávací pipeline.
# Tracky jsou jen v paměti. Křížení a zakrytí osob mohou tento jednoduchý postup zmást.

"""Jednoduchý prostorový tracker. Track ID a důkazy identity existují pouze v paměti."""

from dataclasses import dataclass, field


# IoU je plocha překryvu dělená plochou sjednocení rámečků.
# 0 znamená žádný překryv, 1 totožné rámečky; nejde o podobnost tváří.
def intersection_over_union(first, second):
    """Dva boxy (x, y, šířka, výška) → prostorový překryv 0 až 1."""
    x, y = max(first[0], second[0]), max(first[1], second[1])  # Levý horní roh průniku.
    right = min(first[0] + first[2], second[0] + second[2])  # Pravá hrana průniku.
    bottom = min(first[1] + first[3], second[1] + second[3])  # Dolní hrana průniku.
    intersection = max(0, right - x) * max(0, bottom - y)  # Plocha společné části, px².
    union = first[2] * first[3] + second[2] * second[3] - intersection  # Plocha sjednocení.
    return intersection / union if union > 0 else 0.0


# Stav sledovaného obličeje. dataclass vytvoří jeho datovou třídu.
@dataclass
class Track:
    # ID sledování v tomto běhu aplikace; po restartu se začíná znovu.
    track_id: int
    # Poslední rámeček: (x, y, šířka, výška).
    box: tuple
    last_seen: float  # Monotonic čas poslední přiřazené detekce; není to UTC datum.
    # Uložená osoba, nebo None, dokud rozpoznávání nepotvrdí identitu.
    person_id: str | None = None
    # Nejbližší povolené časy výpočtů brání jejich opakování při každém snímku.
    next_recognition: float = 0.0
    next_quality: float = 0.0
    # Dočasné embeddingy pro založení nové osoby.
    # default_factory=list vytvoří každému tracku vlastní seznam.
    evidence: list = field(default_factory=list)
    # Kandidát existující osoby a počet jasných shod se stejným kandidátem.
    match_person: str | None = None
    match_votes: int = 0
    # Od první chybějící detekce počítáme timeout; ztráta tracku neprokazuje odchod člověka.
    missed_since: float | None = None
    # Příznak nejistého výsledku pro popisek v náhledu.
    ambiguous_identity: bool = False


# Spravuje dočasné tracky a propojuje je s aktuálními detekcemi.
class FaceTracker:
    # ==================== STAV A JEDEN KROK TRACKINGU ====================
    # Začne s prázdným slovníkem tracků a číslem pro první track.
    def __init__(self, settings):
        self.settings = settings  # Settings: práh IoU, odstup kandidátů a timeout.
        self.tracks = {}  # track_id → Track; pouze stav aktuálního běhu v paměti.
        self.next_id = 1  # Nejbližší volné dočasné ID, po restartu se začíná od 1.

    # Vrátí dvojice (track, pozorování). now slouží intervalům, ne jako uložené datum.
    def update(self, observations, now):
        """Seznam FaceObservation + monotonic čas → seznam dvojic (Track, FaceObservation)."""
        self._expire_missing(now)
        # scores[(track_id, index detekce)] = prostorový překryv starého a nového boxu.
        scores = {(key, index): intersection_over_union(track.box, observation.box)
                  for key, track in self.tracks.items() for index, observation in enumerate(observations)}
        possible = {(key, index): score for (key, index), score in scores.items()
                    if score >= self.settings.track_iou}  # Jen dvojice s dostatečným překryvem.
        blocked_observations = self._discard_ambiguous(possible, len(observations))
        assigned = self._assign_existing(possible, blocked_observations, observations, now)
        result = [(track, observations[index]) for index, track in assigned.items()]
        assigned_tracks = {track.track_id for track in assigned.values()}  # Použitá stará ID.
        assigned_observations = set(assigned)  # Použité indexy detekcí.
        self._mark_missing(assigned_tracks, now)
        # Nepřiřazené detekce dostanou nové tracky; tím ještě nevznikají profily osob.
        for index, observation in enumerate(observations):
            if index in assigned_observations or index in blocked_observations:
                continue
            track = Track(self.next_id, observation.box, now)
            self.next_id += 1
            self.tracks[track.track_id] = track
            result.append((track, observation))
        return result

    # ==================== ZÁNIK A NEJEDNOZNAČNÉ PŘEKRYVY ====================

    def _expire_missing(self, now) -> None:
        """Odstraní tracky po timeoutu od skutečně chybějící detekce; vrací None."""
        self.tracks = {key: track for key, track in self.tracks.items()
                       if track.missed_since is None or now - track.missed_since < self.settings.track_timeout}

    def _discard_ambiguous(self, possible, observation_count) -> set:
        """Zruší nejasné tracky a vrátí množinu indexů detekcí, které se nesmějí přiřadit."""
        ambiguous_tracks = set()  # Track ID bez jednoznačného prostorového pokračování.
        blocked_observations = set()  # Indexy detekcí sdílené nejasnými kandidáty.
        # Nejasnost první možnosti: jeden starý track odpovídá více novým rámečkům.
        for key in self.tracks:
            ranked = sorted((score, index) for (track_id, index), score in possible.items() if track_id == key)
            # ranked: (IoU, index detekce), vzestupně; poslední dvě položky jsou nejlepší.
            if len(ranked) > 1 and ranked[-1][0] - ranked[-2][0] < self.settings.track_margin:
                ambiguous_tracks.add(key)
                blocked_observations.update(index for _, index in ranked)
        # Nejasnost opačné možnosti: jedna detekce pasuje k více starým trackům.
        for index in range(observation_count):
            ranked = sorted((score, key) for (key, obs_index), score in possible.items() if obs_index == index)
            if len(ranked) > 1 and ranked[-1][0] - ranked[-2][0] < self.settings.track_margin:
                blocked_observations.add(index)
                ambiguous_tracks.update(key for _, key in ranked)
        # Nejasné vazby zrušíme, abychom vzorek nepřiřadili k nesprávné osobě.
        for key in ambiguous_tracks:
            self.tracks.pop(key, None)
        return blocked_observations

    # ==================== JEDNOZNAČNÁ PŘIŘAZENÍ A ZTRÁTA DETEKCE ====================

    def _assign_existing(self, possible, blocked_observations, observations, now) -> dict:
        """Vrátí mapu index detekce → Track a aktualizuje box/čas použitých tracků."""
        assigned_tracks = set()  # Již použitá track ID v tomto kroku.
        assigned_observations = set()  # Již použité indexy aktuálních detekcí.
        result = {}  # Index detekce → přiřazený Track, v pořadí nejlepšího IoU.
        # Jednoznačné dvojice přiřazujeme od nejlepšího překryvu.
        # Každý track i detekci smíme přiřadit nejvýše jednou.
        # DŮLEŽITÁ SMYČKA: nejlepší IoU první, každé ID a detekce nejvýše jednou.
        for (key, index), score in sorted(possible.items(), key=lambda pair: pair[1], reverse=True):
            # key = track_id; index = pozice detekce; score = jejich IoU.
            if (key not in self.tracks or key in assigned_tracks or index in assigned_observations
                    or index in blocked_observations):
                continue
            track = self.tracks[key]
            track.box, track.last_seen, track.missed_since = observations[index].box, now, None
            assigned_tracks.add(key)
            assigned_observations.add(index)
            result[index] = track
        return result

    def _mark_missing(self, assigned_tracks, now) -> None:
        """Nepřiřazeným trackům spustí timeout a smaže rozpracované důkazy; vrací None."""
        for key, track in self.tracks.items():
            if key not in assigned_tracks and track.missed_since is None:
                # Chybějící detekce spustí timeout a vymaže rozpracované důkazy identity.
                track.missed_since = now
                # Oddělené série nespolehlivých pozorování nesmějí spojit hlasy identity.
                track.evidence.clear()
                track.match_votes = 0
                track.match_person = None
