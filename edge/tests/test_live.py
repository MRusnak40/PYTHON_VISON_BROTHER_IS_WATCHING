# AUTOMATICKÉ TESTY ŽIVÉ PIPELINE A VLÁKEN.
# Umělé detekce a vektory prověřují logiku identity, nikoli přesnost skutečného modelu.
# MagicMock a patch nahrazují kameru, modely či hodiny. Event synchronizuje vlákna.
# Dočasné složky oddělují testovací profily od skutečných dat.

"""Live identity, frame skipping and original-resolution sample regressions."""

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from edge import main as application
from edge.config.settings import Settings
from edge.vision.faces import FaceCandidate, FaceObservation, FaceProcessor
from edge.vision.live import LiveWorker
from edge.vision.pipeline import VisionPipeline
from edge.vision.profiles import ProfileStore
from edge.vision.tracking import FaceTracker


# Vyrobí umělou detekci s nastavitelným pohledem, kvalitou, otiskem a rámečkem.
def observation(view="front", score=0.85, fingerprint="0000000000000000", box=(0, 0, 112, 112)):
    return FaceObservation(
        np.full((112, 112, 3), 128, dtype=np.uint8), box, 0.99, {},
        {"score": score, "usable": score >= 0.50, "view": view, "fingerprint": fingerprint},
    )


# Jednoduchá náhrada modelu: vrací předem určené detekce a vektor, počítá volání.
class FakeProcessor:
    # Připraví jednu umělou tvář, krátký embedding a nulová počítadla.
    def __init__(self):
        self.observations = [observation()]
        self.vector = [1.0, 0.0, 0.0]
        self.embedding_calls = 0
        self.quality_calls = 0

    # Místo práce detektoru vrátí aktuálně nastavená pozorování.
    def detect(self, frame):
        return self.observations

    # Vrátí předem připravenou kvalitu a započítá kontrolu.
    def evaluate(self, face):
        self.quality_calls += 1
        return face.quality

    # Vrátí kandidáta s kopií nastaveného vektoru a započítá výpočet.
    def embed(self, face):
        self.embedding_calls += 1
        return FaceCandidate(face.crop, face.box, face.quality, self.vector.copy())


# Scénáře vzniku, potvrzování a opětovného rozpoznání identity tracku.
class IdentityTests(unittest.TestCase):
    # Před každým testem vytvoří samostatné úložiště, náhradní model a skutečnou pipeline.
    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory())
        self.settings = Settings(rtsp_url="", data_dir=Path(temporary), embedding_size=3)
        self.store = ProfileStore(self.settings)
        self.processor = FakeProcessor()
        self.pipeline = VisionPipeline(self.processor, self.store, self.settings)
        self.now = datetime(2026, 10, 19, tzinfo=timezone.utc)

    # Provede jedno pozorování s umělým časem; není nutné čekat skutečné sekundy.
    def step(self, seconds, faces=None):
        if faces is not None:
            self.processor.observations = faces
        return self.pipeline.process(None, self.now + timedelta(seconds=seconds), seconds)

    # Třemi konzistentními pozorováními založí profil a vrátí jeho ID.
    def establish(self):
        for seconds in (0, 0.5, 1.0):
            self.step(seconds)
        self.assertEqual(len(self.store.profiles), 1)
        return self.store.profiles[0]["person_id"]

    # Osoba vznikne až po třetím vhodném pozorování, nikoli po prvním snímku.
    def test_one_frame_never_creates_a_person_and_new_person_needs_three(self):
        self.step(0)
        self.assertEqual(self.store.profiles, [])
        self.step(0.5)
        self.assertEqual(self.store.profiles, [])
        _, events = self.step(1.0)
        self.assertEqual(len(self.store.profiles), 1)
        self.assertEqual(events[0]["status"], "created")

    # Potvrzený track při změně pohledu aktualizuje stejnou osobu bez nového matchingu.
    def test_bound_track_keeps_person_across_angles_even_with_nonmatching_embeddings(self):
        person_id = self.establish()
        with patch.object(self.store, "match", side_effect=AssertionError("bound track searched gallery")):
            self.processor.vector = [0.0, 1.0, 0.0]
            self.step(3.5, [observation("left")])
            self.processor.vector = [0.0, 0.0, 1.0]
            self.step(6.0, [observation("right")])
            self.step(8.5, [observation("front", score=0.97)])
        self.assertEqual(len(self.store.profiles), 1)
        samples = self.store.profiles[0]["face_samples"]
        self.assertEqual({sample["role"] for sample in samples}, {"left", "front", "right"})
        self.assertTrue(all(track.person_id == person_id for track in self.pipeline.tracker.tracks.values()))
        self.assertEqual(len(list((self.settings.data_dir / "profiles" / person_id).glob("*.jpg"))), 3)

    # Po zániku tracku nový track potvrdí původní osobu dvěma shodami; track_id se neukládá.
    def test_return_after_track_expiration_matches_existing_person_with_two_votes(self):
        person_id = self.establish()
        self.step(1.25, [])
        self.step(3.0, [])
        self.assertEqual(self.pipeline.tracker.tracks, {})
        self.step(4.0, [observation()])
        track = next(iter(self.pipeline.tracker.tracks.values()))
        self.assertIsNone(track.person_id)
        self.step(4.5)
        self.assertEqual(track.person_id, person_id)
        self.assertEqual(len(self.store.profiles), 1)
        self.assertNotIn("track_id", json.dumps(self.store.data))

    # Prostorově odlišný track s jiným embeddingem může po potvrzení založit novou osobu.
    def test_different_person_gets_new_profile_after_track_change(self):
        first = self.establish()
        self.processor.vector = [0.0, 1.0, 0.0]
        for seconds in (2.0, 2.5, 3.0):
            self.step(seconds, [observation(box=(250, 0, 112, 112))])
        self.assertEqual(len(self.store.profiles), 2)
        ids = {profile["person_id"] for profile in self.store.profiles}
        self.assertIn(first, ids)
        self.assertEqual(len(ids), 2)

    # Špatný obraz může dál tvořit track, ale nesmí zbytečně vytvářet embeddingy a osoby.
    def test_poor_frames_keep_track_without_embedding_or_person_creation(self):
        for tick in range(20):
            self.step(tick * 0.25, [observation(score=0.35)])
        self.assertEqual(self.store.profiles, [])
        self.assertEqual(self.processor.embedding_calls, 0)
        self.assertEqual(list(self.pipeline.tracker.tracks), [1])

    # Střídání neslučitelných embeddingů nevede k založení osoby.
    def test_inconsistent_evidence_does_not_create_person(self):
        for tick in range(8):
            self.processor.vector = [1.0, 0.0, 0.0] if tick % 2 else [0.0, 1.0, 0.0]
            self.step(tick * 0.5)
        self.assertEqual(self.store.profiles, [])

    # Dva podobné profily nezpůsobí založení třetího při nejisté shodě.
    def test_ambiguous_gallery_does_not_create_another_person(self):
        face = self.processor.embed(observation())
        self.store.observe(face, self.now)
        face.embedding = [0.0, 1.0, 0.0]
        self.store.observe(face, self.now)
        self.store.profiles[1]["face_samples"][0]["embedding"] = [0.99, 0.01, 0.0]
        for tick in range(6):
            self.step(tick * 0.5)
        self.assertEqual(len(self.store.profiles), 2)
        self.assertIsNone(next(iter(self.pipeline.tracker.tracks.values())).person_id)

    # Rychlé příchody snímků nepřekročí stanovený interval pokusů o identitu.
    def test_recognition_interval_limits_unresolved_track(self):
        for tick in range(5):
            self.step(tick * 0.05)
        self.assertEqual(self.processor.embedding_calls, 1)
        self.assertEqual(self.store.profiles, [])

    # Po potvrzení tracku stejný obraz dál nevyvolává zbytečné embeddingy a matching.
    def test_resolved_track_does_not_repeat_identity_for_unchanged_samples(self):
        # wraps ponechá skutečný výpočet metody a současně zaznamená počet jejích volání.
        with patch.object(self.store, "match", wraps=self.store.match) as matching:
            for tick in range(100):
                self.step(tick * 0.25)
            self.assertEqual(self.processor.embedding_calls, 3)
            # Three evidence matches and one final recheck before creating the profile.
            self.assertEqual(matching.call_count, 4)
        self.assertEqual(len(self.store.profiles), 1)
        self.assertLess(self.processor.quality_calls, 40)

    # Při nejasném překryvu se vazby zruší a další detekce začínají s novými tracky.
    def test_missing_detection_expires_binding_and_overlapping_tracks_are_not_reused(self):
        tracker = FaceTracker(self.settings)
        initial = tracker.update([observation(box=(0, 0, 100, 100)),
                                  observation(box=(60, 0, 100, 100))], 0)
        initial[0][0].person_id = "person-0001"
        initial[1][0].person_id = "person-0002"
        self.assertEqual(tracker.update([observation(box=(30, 0, 100, 100))], 0.25), [])
        self.assertEqual(tracker.tracks, {})
        renewed = tracker.update([observation(box=(0, 0, 100, 100)),
                                  observation(box=(60, 0, 100, 100))], 0.5)
        self.assertTrue(all(track.person_id is None and track.track_id > 2 for track, _ in renewed))


# Ověřuje souběžné předávání snímků, ukončení a hlášení chyb.
class WorkerTests(unittest.TestCase):
    # Během povinné pauzy se čekající snímek může přepsat novějším.
    def test_processing_interval_waits_while_newer_frames_replace_pending(self):
        first, second = Event(), Event()
        # Umělé hodiny lze v testu posunout bez čekání v reálném čase.
        clock = [100.0]
        frames = []
        pipeline = MagicMock()
        pipeline.stats = {"frames": 0, "embeddings": 0, "matches": 0,
                          "embedding_seconds": 0.0, "detection_seconds": 0.0}

        # Náhradní výpočet zaznamená nebo signalizuje práci; podle scénáře může čekat na uvolnění.
        def process(frame, *args):
            frames.append(frame)
            (first if len(frames) == 1 else second).set()
            return [], []

        pipeline.process.side_effect = process
        with patch("edge.vision.live.monotonic", side_effect=lambda: clock[0]):
            worker = LiveWorker(pipeline, Settings(rtsp_url="", process_interval=0.25))
            worker.start()
            try:
                worker.submit(1, None, 100)
                self.assertTrue(first.wait(timeout=2))
                worker.submit(2, None, 100.1)
                worker.submit(3, None, 100.2)
                self.assertFalse(second.wait(timeout=0.05))
                clock[0] = 100.3
                with worker.condition:
                    worker.condition.notify_all()
                self.assertTrue(second.wait(timeout=2))
            finally:
                worker.close()
        self.assertEqual(frames, [1, 3])

    # I při zaměstnaném výpočetním vlákně náhled vykreslí obraz a přijme Q.
    def test_main_renders_and_handles_quit_while_inference_is_busy(self):
        started, release = Event(), Event()
        finished = Event()  # Poslední zápis smí přijít až po dokončení rozpracované inference.
        pipeline, gui, source, store = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        pipeline.stats = {}
        source.reported_fps = 25.0
        source.read.return_value = np.zeros((112, 112, 3), dtype=np.uint8)

        # Náhradní výpočet zaznamená nebo signalizuje práci; podle scénáře může čekat na uvolnění.
        def process(*args):
            started.set()
            if not release.wait(timeout=3):
                raise RuntimeError("test inference not released")
            finished.set()
            return [], []

        # Napodobí stisk Q během rozpracovaného výpočtu a povolí jeho dokončení.
        def quit_in_preview(*args):
            try:
                self.assertTrue(started.wait(timeout=2))
                gui.imshow.assert_called_once()
                return ord("q")
            finally:
                release.set()

        pipeline.process.side_effect = process
        store.flush.side_effect = lambda *args, **kwargs: self.assertTrue(finished.is_set())
        gui.waitKey.side_effect = quit_in_preview
        with patch.object(application, "load_settings", return_value=Settings(rtsp_url="")), \
             patch.object(application, "ProfileStore", return_value=store), \
             patch.object(application, "FaceProcessor"), \
             patch.object(application, "VisionPipeline", return_value=pipeline), \
             patch.object(application, "RTSPSource", return_value=source), \
             patch.object(application, "cv2", gui):
            self.assertEqual(application.main(), 0)
        self.assertTrue(release.is_set())
        source.close.assert_called_once()
        store.flush.assert_called_once()

    # Při zahlcení nezůstane dlouhá fronta: po prvním snímku přijde na řadu nejnovější.
    def test_busy_worker_keeps_only_the_latest_pending_frame(self):
        first_started, release_first, second_finished = Event(), Event(), Event()
        frames = []
        pipeline = MagicMock()
        pipeline.stats = {"frames": 0, "embeddings": 0, "matches": 0,
                          "embedding_seconds": 0.0, "detection_seconds": 0.0}

        # Náhradní výpočet zaznamená nebo signalizuje práci; podle scénáře může čekat na uvolnění.
        def process(frame, now, timestamp):
            frames.append(frame)
            if len(frames) == 1:
                first_started.set()
                if not release_first.wait(timeout=3):
                    raise RuntimeError("test worker was not released")
            else:
                second_finished.set()
            return [], []

        pipeline.process.side_effect = process
        worker = LiveWorker(pipeline, Settings(rtsp_url="", process_interval=0))
        worker.start()
        try:
            worker.submit(1, None, 1)
            self.assertTrue(first_started.wait(timeout=2))
            for number in range(2, 101):
                # Místo obrázku tu stačí číslo, protože zkoušíme předávání snímků, nikoli jejich obsah.
                worker.submit(number, None, number)
            self.assertEqual(worker.pending[0], 100)
            self.assertEqual(frames, [1])
            release_first.set()
            self.assertTrue(second_finished.wait(timeout=2))
        finally:
            release_first.set()
            worker.close()
        self.assertEqual(frames, [1, 100])
        self.assertEqual(worker.dropped, 98)
        self.assertIsNone(worker.snapshot()[2])

    # Chyba workeru se uloží do snapshot a vlákno se dá řádně ukončit.
    def test_worker_reports_failure_to_main_and_stops(self):
        pipeline = MagicMock()
        pipeline.stats = {}
        failed = Event()

        # Záměrně vyvolá výjimku pro ověření přenosu chyby do hlavního vlákna.
        def fail(*args):
            failed.set()
            raise TypeError("private exception text")

        pipeline.process.side_effect = fail
        worker = LiveWorker(pipeline, Settings(rtsp_url=""))
        worker.start()
        worker.submit(None, None, 0)
        self.assertTrue(failed.wait(timeout=2))
        worker.close()
        self.assertIsInstance(worker.snapshot()[2], TypeError)


# Ověřuje bezpečný import aplikace a zachování rozměrů původních výřezů.
class SourceIndependenceTests(unittest.TestCase):
    # Import obou vstupů nesmí otevřít spojení s kamerou.
    def test_imports_do_not_open_camera(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-c",
             "import sys\nfrom unittest.mock import patch\n"
             "with patch('cv2.VideoCapture') as capture:\n"
             "    import edge.main\n"
             "    sys.path.insert(0, 'edge')\n"
             "    import main\n"
             "    capture.assert_not_called()\n"
             "print('generic OK')"],
            cwd=root, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("generic OK", result.stdout)

    # Detektor dostane menší obraz, ale souřadnice, výřez i uložený JPEG mají původní měřítko.
    def test_scaled_detection_crops_and_saves_original_resolution(self):
        processor = FaceProcessor.__new__(FaceProcessor)
        processor.detection_width = 320
        processor.model_name = "Facenet512"
        processor.detector = MagicMock()
        processor.deepface = MagicMock()
        processor.detector.detect_faces.return_value = [
            {"box": [10, 20, 40, 60], "confidence": np.float32(0.99),
             "keypoints": {"nose": [30, 45]}},
        ]
        processor.deepface.represent.return_value = [{"embedding": [1.0, 0.0, 0.0]}]
        frame = np.random.default_rng(4).integers(50, 200, (480, 960, 3), dtype=np.uint8)
        faces = list(processor.detect(frame))
        self.assertEqual(processor.detector.detect_faces.call_args.args[0].shape, (160, 320, 3))
        self.assertEqual(faces[0].box, (30, 60, 120, 180))
        self.assertEqual(faces[0].crop.shape, (180, 120, 3))
        self.assertEqual(faces[0].keypoints["nose"], (90.0, 135.0))
        processor.deepface.represent.assert_not_called()
        candidate = processor.embed(faces[0])
        with tempfile.TemporaryDirectory() as folder:
            store = ProfileStore(Settings(rtsp_url="", data_dir=Path(folder), embedding_size=3))
            store.observe(candidate, datetime.now(timezone.utc))
            sample = store.profiles[0]["face_samples"][0]
            stored = cv2.imdecode(np.frombuffer((Path(folder) / sample["path"]).read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
            self.assertEqual(stored.shape, (180, 120, 3))


# Přímé spuštění souboru provede jeho testy.
if __name__ == "__main__":
    unittest.main()
