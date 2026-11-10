# AUTOMATICKÉ TESTY PROFILŮ, FOTEK A KVALITY.
# Používají umělé obrázky a krátké vektory; neověřují přesnost rozpoznávání skutečných lidí.
# Každý test pracuje v dočasné složce a nezasahuje do skutečných profilů.
# assertEqual ověřuje rovnost, assertTrue pravdivost a assertRaises očekávanou výjimku.

"""Storage/matching regression tests using synthetic images and embeddings."""

import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np

from edge.config.settings import Settings
from edge.vision.faces import FaceCandidate
from edge.vision.profiles import ProfileStore
from edge.vision.quality import evaluate_face


# Ověřuje chování úložiště při běžném používání i poškozených datech.
class ProfileTests(unittest.TestCase):
    # unittest tuto přípravu spustí před každým testem, takže testy mají nezávislá data.
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        # Úklid dočasných souborů proběhne i při neúspěchu testu.
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        # Zkrácené vektory se třemi čísly stačí k ověření logiky; model zde neběží.
        self.settings = Settings(rtsp_url="", data_dir=self.root, embedding_size=3)
        self.store = ProfileStore(self.settings)
        self.now = datetime(2026, 10, 19, tzinfo=timezone.utc)

    # Vytvoří umělého kandidáta s nastavitelnou kvalitou, pohledem a embeddingem.
    def face(self, score=0.65, fingerprint="0000000000000000", view="front", embedding=None):
        return FaceCandidate(
            np.full((100, 100, 3), 128, dtype=np.uint8), (0, 0, 100, 100),
            {"score": score, "usable": True, "fingerprint": fingerprint, "view": view},
            embedding or [1.0, 0.0, 0.0],
        )

    # Předá kandidáta úložišti s časem posunutým o daný počet sekund.
    def observe(self, face, seconds=0):
        return self.store.observe(face, self.now + timedelta(seconds=seconds))

    # Po novém načtení úložiště zůstane identita stejná a cesty k fotkám relativní.
    def test_restart_matches_same_person_and_keeps_relative_paths(self):
        result = self.observe(self.face())
        self.assertEqual(result["status"], "created")
        self.store = ProfileStore(self.settings)
        self.assertEqual(self.observe(self.face(), 10)["status"], "matched")
        self.assertEqual(len(self.store.profiles), 1)
        profile = self.store.profiles[0]
        self.assertEqual(profile["person_id"], "person-0001")
        relative = profile["face_samples"][0]["path"]
        self.assertFalse(Path(relative).is_absolute())
        self.assertTrue((self.root / relative).is_file())
        self.assertEqual(profile["representative_image"], relative)

    # Číselné typy NumPy nezpůsobí chybu JSON a profily lze znovu načíst.
    def test_numpy_detector_confidence_can_be_persisted_and_reloaded(self):
        crop = np.random.default_rng(7).integers(50, 200, (112, 112, 3), dtype=np.uint8)
        for index, scalar_type in enumerate((np.float32, np.float64)):
            with self.subTest(scalar_type=scalar_type.__name__):
                quality = evaluate_face(crop, scalar_type(0.99), {})
                self.assertIs(type(quality["score"]), float)
                self.assertIs(type(quality["usable"]), bool)
                json.dumps(quality, allow_nan=False)
                embedding = [1.0, 0.0, 0.0] if index == 0 else [0.0, 1.0, 0.0]
                candidate = FaceCandidate(crop, (0, 0, 112, 112), quality, embedding)
                self.assertEqual(self.observe(candidate, index * 3)["status"], "created")
                self.store = ProfileStore(self.settings)
        self.assertEqual(len(self.store.profiles), 2)

    # Podobná fotka se vymění až po dostatečném zlepšení a časovém odstupu.
    def test_duplicate_is_replaced_only_after_meaningful_improvement_and_interval(self):
        self.observe(self.face())
        original = copy.deepcopy(self.store.profiles[0])
        self.assertEqual(self.observe(self.face(0.68), 3)["status"], "matched")
        self.assertEqual(self.observe(self.face(0.90), 1)["status"], "matched")
        self.assertEqual(self.observe(self.face(0.90), 3)["status"], "sample_replaced")
        samples = self.store.profiles[0]["face_samples"]
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["quality"]["score"], 0.90)
        self.assertFalse((self.root / original["representative_image"]).exists())
        self.assertEqual(len(list((self.root / "profiles/person-0001").glob("*.jpg"))), 1)

    # Ani po naplnění pěti míst se nezastaví výměna za kvalitnější vzorky.
    def test_five_samples_continue_improving(self):
        hashes = ["0000000000000000", "ffffffffffffffff", "aaaaaaaaaaaaaaaa",
                  "5555555555555555", "00000000ffffffff", "ffffffff00000000"]
        views = ["front", "left", "right", "front", "front"]
        scores = [0.90, 0.85, 0.80, 0.65, 0.70]
        for i, (fingerprint, view, score) in enumerate(zip(hashes, views, scores)):
            self.observe(self.face(score, fingerprint, view), i * 3)
        self.assertEqual(len(self.store.profiles[0]["face_samples"]), 5)
        result = self.observe(self.face(0.77, hashes[5]), 18)
        self.assertEqual(result["status"], "sample_replaced")
        samples = self.store.profiles[0]["face_samples"]
        self.assertEqual(len(samples), 5)
        self.assertEqual(min(s["quality"]["score"] for s in samples), 0.70)
        best = max(samples, key=lambda s: s["quality"]["score"])
        self.assertEqual(self.store.profiles[0]["representative_image"], best["path"])
        self.assertEqual(len(list((self.root / "profiles/person-0001").glob("*.jpg"))), 5)
        ProfileStore(self.settings)

    # Tři hlavní pohledy fungují bez povinných doplňků a doplňky je nevytlačí.
    def test_three_primary_views_are_enough_and_survive_extra_candidates(self):
        for i, view in enumerate(("left", "front", "right")):
            self.observe(self.face(0.70, view=view), i * 3)
        samples = self.store.profiles[0]["face_samples"]
        self.assertEqual({s["role"] for s in samples}, {"left", "front", "right"})
        self.assertEqual(len(samples), 3)
        self.assertEqual(self.observe(self.face(0.72), 12)["status"], "matched")
        self.assertEqual(len(self.store.profiles[0]["face_samples"]), 3)
        self.assertEqual(self.observe(self.face(0.90, view="left"), 15)["status"], "sample_replaced")
        self.assertEqual(len(self.store.profiles[0]["face_samples"]), 3)

    # Fotky z jedné strany nesmějí zabrat místa pro chybějící hlavní pohledy.
    def test_single_view_cannot_take_slots_reserved_for_missing_sides(self):
        self.observe(self.face(0.90))
        for i, fingerprint in enumerate(("ffffffffffffffff", "aaaaaaaaaaaaaaaa", "5555555555555555")):
            self.observe(self.face(0.70, fingerprint), (i + 1) * 3)
        self.assertEqual(len(self.store.profiles[0]["face_samples"]), 3)
        self.observe(self.face(0.55, view="left"), 12)
        self.observe(self.face(0.55, view="right"), 15)
        samples = self.store.profiles[0]["face_samples"]
        self.assertEqual(len(samples), 5)
        self.assertEqual(sum(s["role"] == "extra" for s in samples), 2)
        self.assertTrue({"left", "front", "right"}.issubset(s["role"] for s in samples))

    # I starší plný profil doplní chybějící strany a zachová nejlepší přední pohled.
    def test_legacy_full_gallery_can_gain_missing_sides_without_losing_best_front(self):
        self.observe(self.face(0.90))
        profile = self.store.profiles[0]
        best_path = profile["representative_image"]
        # Legacy gallery: five distinct front samples, before roles were introduced.
        for i in range(4):
            sample = copy.deepcopy(profile["face_samples"][0])
            sample["path"] = f"profiles/person-0001/legacy_{i}.jpg"
            (self.root / sample["path"]).write_bytes((self.root / best_path).read_bytes())
            sample["quality"]["score"] = 0.60 + i * 0.05
            profile["face_samples"].append(sample)
        for sample in profile["face_samples"]:
            sample.pop("role", None)
        self.store.path.write_text(json.dumps(self.store.data), encoding="utf-8")
        self.store = ProfileStore(self.settings)
        self.assertEqual(len(self.store.profiles[0]["face_samples"]), 5)
        self.assertEqual(self.observe(self.face(0.55, view="left"), 3)["status"], "sample_replaced")
        self.assertEqual(self.observe(self.face(0.55, view="right"), 6)["status"], "sample_replaced")
        samples = self.store.profiles[0]["face_samples"]
        self.assertEqual({s["role"] for s in samples}, {"left", "front", "right", "extra"})
        self.assertEqual(sum(s["role"] == "extra" for s in samples), 2)
        self.assertTrue((self.root / best_path).is_file())
        self.assertEqual(self.store.profiles[0]["representative_image"], best_path)
        self.assertEqual(len(list((self.root / "profiles/person-0001").glob("*.jpg"))), 5)

    # Odlišný pohled lze doplnit, i když mají obrázky stejný jednoduchý otisk.
    def test_different_view_can_add_sample_even_when_hash_matches(self):
        self.observe(self.face())
        self.assertEqual(self.observe(self.face(view="left"), 3)["status"], "sample_added")
        self.assertEqual(len(self.store.profiles[0]["face_samples"]), 2)

    # Odlišná osoba dostane nový profil; existující složka zabrání opětovnému použití ID.
    def test_other_identity_gets_new_profile_and_reserved_directory_is_skipped(self):
        (self.root / "profiles/person-0001").mkdir(parents=True)
        self.assertEqual(self.observe(self.face())["person_id"], "person-0002")
        other = self.observe(self.face(embedding=[0.0, 1.0, 0.0]), 3)
        self.assertEqual(other["person_id"], "person-0003")
        self.assertEqual(len(self.store.profiles), 2)

    # Nejasná shoda nesmí upravit některou ze dvou podobných osob ani založit další.
    def test_ambiguous_match_does_not_create_or_update_profile(self):
        self.observe(self.face())
        self.observe(self.face(embedding=[0.0, 1.0, 0.0]), 3)
        # A second stored identity close to the first simulates an ambiguous gallery.
        self.store.profiles[1]["face_samples"][0]["embedding"] = [0.99, 0.01, 0.0]
        before = copy.deepcopy(self.store.data)
        self.assertEqual(self.observe(self.face(), 6)["status"], "ambiguous")
        self.assertEqual(self.store.data, before)

    # Když selže zápis JSON, původní profil i jeho fotka musí zůstat zachované.
    def test_json_failure_preserves_old_profile_and_image(self):
        self.observe(self.face())
        old_json = self.store.path.read_bytes()
        old_image = self.root / self.store.profiles[0]["representative_image"]
        with patch.object(self.store, "_write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.observe(self.face(0.95), 3)
        self.assertEqual(self.store.path.read_bytes(), old_json)
        self.assertTrue(old_image.is_file())
        self.assertEqual(len(list(old_image.parent.glob("*.jpg"))), 1)
        ProfileStore(self.settings)

    # Rozlišuje chybějící, prázdný a vadný JSON; chybějící fotka zachová použitelný embedding.
    def test_missing_blank_corrupt_store_and_missing_image(self):
        self.store.path.parent.mkdir(parents=True)
        self.store.path.write_text("", encoding="utf-8")
        self.assertEqual(ProfileStore(self.settings).profiles, [])
        self.store.path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            ProfileStore(self.settings)
        self.assertEqual(self.store.path.read_text(), "{broken")
        self.observe(self.face())
        (self.root / self.store.profiles[0]["representative_image"]).unlink()
        self.store = ProfileStore(self.settings)
        self.assertEqual(self.store.missing_images, 1)
        self.assertEqual(self.store.match([1.0, 0.0, 0.0])[0], 0)
        self.assertEqual(self.observe(self.face(0.60), 3)["status"], "sample_replaced")
        self.assertTrue((self.root / self.store.profiles[0]["representative_image"]).is_file())

    # Časy se ukládají podle intervalu a dodatečná metadata zůstávají zachovaná.
    def test_last_seen_flush_and_extra_fields_survive(self):
        self.observe(self.face())
        self.store.data["custom"] = "preserve"
        self.store.profiles[0]["note"] = "preserve"
        self.observe(self.face(), 10)
        self.store.flush(self.now + timedelta(seconds=10), force=True)
        data = json.loads(self.store.path.read_text(encoding="utf-8"))
        self.assertEqual(data["custom"], "preserve")
        self.assertEqual(data["profiles"][0]["note"], "preserve")
        self.assertEqual(data["profiles"][0]["last_seen"], (self.now + timedelta(seconds=10)).isoformat())

    # Nekvalitní výřez nebo vadný vektor nesmí založit osobu.
    def test_poor_or_invalid_candidate_does_not_create_profile(self):
        poor = self.face()
        poor.quality["usable"] = False
        self.assertEqual(self.observe(poor)["status"], "poor_quality")
        with self.assertRaises(ValueError):
            self.observe(self.face(embedding=[float("nan"), 0.0, 1.0]))
        self.assertEqual(self.store.profiles, [])
        self.assertFalse(self.store.path.exists())

    # Cesta mimo složku a nesprávný model se odmítnou bez přepsání původních dat.
    def test_reject_path_escape_and_model_mismatch_without_overwrite(self):
        self.observe(self.face())
        for edit in (lambda p: p.update(embedding_model="other"),
                     lambda p: p["face_samples"][0].update(path="../outside.jpg")):
            data = copy.deepcopy(self.store.data)
            edit(data["profiles"][0])
            self.store.path.write_text(json.dumps(data), encoding="utf-8")
            before = self.store.path.read_bytes()
            with self.assertRaises(ValueError):
                ProfileStore(self.settings)
            self.assertEqual(self.store.path.read_bytes(), before)


# Ověřuje jednoduchá pravidla kvality na umělých obrázcích.
class QualityTests(unittest.TestCase):
    # Posouváním umělého nosu vůči očím ověřuje hrubé určení left/front/right.
    def test_view_hint_from_landmarks(self):
        texture = np.random.default_rng(7).integers(50, 200, (112, 112, 3), dtype=np.uint8)
        for nose_x, expected in ((35, "left"), (56, "front"), (77, "right")):
            result = evaluate_face(texture, 0.99, {
                "left_eye": (30, 30), "right_eye": (82, 30), "nose": (nose_x, 55),
            })
            self.assertEqual(result["view"], expected)

    # Odmítá jednolitý, tmavý a malý obraz či nejistou detekci a přijme vhodnou texturu.
    def test_blank_dark_small_and_sharp_crops(self):
        blank = np.full((112, 112, 3), 128, dtype=np.uint8)
        self.assertFalse(evaluate_face(blank, 1.0, {})["usable"])
        texture = np.random.default_rng(7).integers(50, 200, (112, 112, 3), dtype=np.uint8)
        self.assertTrue(evaluate_face(texture, 0.99, {})["usable"])
        self.assertFalse(evaluate_face(texture[:40, :40], 0.99, {})["usable"])
        self.assertFalse(evaluate_face(texture, 0.5, {})["usable"])
        self.assertFalse(evaluate_face(np.zeros_like(texture), 1.0, {})["usable"])


# Přímé spuštění souboru zavolá testovací nástroj unittest.
if __name__ == "__main__":
    unittest.main()
