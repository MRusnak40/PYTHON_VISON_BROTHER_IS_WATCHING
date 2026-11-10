# AUTOMATICKÉ TESTY SPUŠTĚNÍ A RTSP ČTENÍ.
# Testy napodobují kameru i okno; neposílají požadavky skutečné kameře.
# MagicMock je náhradní objekt, patch dočasně nahradí skutečnou funkci.
# assert... kontroluje očekávaný výsledek; nesplněná podmínka znamená neúspěšný test.
# Dočasné složky brání změnám skutečných profilů.

"""Exercise RTSP errors and the application loop without a camera or GUI."""

import tempfile
import os
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

import numpy as np

from edge import main as application
from edge.cameras.source import RTSPSource, StreamError
from edge.config.settings import Settings, SettingsError, load_settings
from edge.vision.faces import FaceCandidate, FaceObservation, FaceProcessor
from edge.vision.profiles import ProfileStore


# Scénáře otevírání, přijímání a selhání streamu s napodobeným OpenCV.
class SourceTests(unittest.TestCase):
    # I neúspěšně otevřený zdroj musí jít uklidit a uvolnit.
    def test_failed_open_can_be_closed(self):
        capture = MagicMock()
        capture.isOpened.return_value = False
        with patch("edge.cameras.source.cv2.VideoCapture", return_value=capture):
            source = RTSPSource("rtsp://unused.invalid/stream")
            with self.assertRaises(StreamError):
                source.open()
            source.close()
        capture.release.assert_called_once()

    # Z několika přijatých snímků se vrátí nejnovější; odpojení uvolní spojení.
    def test_reader_keeps_latest_frame_and_releases_on_disconnect(self):
        capture = MagicMock()
        capture.isOpened.return_value = True
        # Event je signál mezi vlákny: set ho aktivuje, wait čeká na jeho aktivaci.
        produced = Event()
        finish = Event()
        first = np.full((2, 2, 3), 1, dtype=np.uint8)
        newest = np.full((2, 2, 3), 2, dtype=np.uint8)
        calls = 0

        # Napodobí příchod dvou snímků a poté odpojení. Event řídí okamžik pokračování.
        def receive():
            nonlocal calls
            calls += 1
            if calls == 1:
                return True, first
            if calls == 2:
                return True, newest
            produced.set()
            finish.wait(timeout=2)
            return False, None

        # side_effect určí, co se má při volání náhradní metody skutečně provést.
        capture.read.side_effect = receive
        with patch("edge.cameras.source.cv2.VideoCapture", return_value=capture):
            source = RTSPSource("rtsp://unused.invalid/stream")
            try:
                source.open()
                self.assertTrue(produced.wait(timeout=2))
                np.testing.assert_array_equal(source.read(), newest)
                finish.set()
                source.thread.join(timeout=2)
                with self.assertRaises(StreamError):
                    source.read()
            finally:
                finish.set()
                source.close()
        capture.release.assert_called_once()

    # Chyba dekodéru se ohlásí bez vyzrazení citlivého textu knihovny.
    def test_decoder_exception_has_sanitized_message(self):
        capture = MagicMock()
        capture.isOpened.return_value = True
        capture.read.side_effect = RuntimeError("secret-camera-url")
        with patch("edge.cameras.source.cv2.VideoCapture", return_value=capture):
            source = RTSPSource("rtsp://unused.invalid/stream")
            source.open()
            with self.assertRaises(StreamError) as raised:
                source.read()
            source.close()
        self.assertNotIn("secret", str(raised.exception))


# Scénáře hlavní aplikace s nahrazenou kamerou, modely a grafickým oknem.
class ApplicationTests(unittest.TestCase):
    def test_preview_scales_boxes_without_changing_original_frame(self):
        """Kreslení do zmenšeného náhledu nesmí měnit vstup používaný workerem."""
        app = application.EdgeApplication()
        app.settings = Settings(rtsp_url="", preview_width=200)
        frame = np.zeros((200, 400, 3), dtype=np.uint8)
        original = frame.copy()
        with patch.object(application.cv2, "imshow") as show:
            app._show_preview(frame, [((40, 60, 80, 100), "T1 person-0001")], 10.0, 10.1)
        display = show.call_args.args[1]
        self.assertEqual(display.shape, (100, 200, 3))
        np.testing.assert_array_equal(display[30, 20], [0, 220, 0])
        np.testing.assert_array_equal(frame, original)

    def test_stale_labels_are_not_drawn_on_new_frame(self):
        """Po timeoutu zůstane náhled bez starého rámečku, ale dál se zobrazuje."""
        app = application.EdgeApplication()
        app.settings = Settings(rtsp_url="")
        frame = np.zeros((112, 112, 3), dtype=np.uint8)
        with patch.object(application.cv2, "imshow") as show:
            app._show_preview(frame, [((10, 10, 80, 80), "old")], 10.0, 12.0)
        np.testing.assert_array_equal(show.call_args.args[1], frame)

    def test_unexpected_rtsp_failure_reports_connection_stage_without_secrets(self):
        """Chyba spojení patří RTSP fázi; URL se nesmí vypsat."""
        from io import StringIO

        with patch.object(application, "load_settings", return_value=Settings(rtsp_url="")), \
             patch.object(application, "ProfileStore"), \
             patch.object(application, "FaceProcessor"), \
             patch.object(application, "LiveWorker") as worker, \
             patch.object(application, "RTSPSource") as source, \
             patch.object(application, "cv2"), \
             patch("sys.stdout", new_callable=StringIO) as output:
            source.return_value.open.side_effect = RuntimeError("secret-url")
            worker.return_value.snapshot.return_value = ([], 0.0, None)
            self.assertEqual(application.main(), 1)
        self.assertIn("otevirani RTSP spojeni: RuntimeError", output.getvalue())
        self.assertNotIn("secret", output.getvalue())
        source.return_value.close.assert_called_once()

    # Konfigurace načte místní .env; již nastavené prostředí má přednost.
    def test_config_directory_env_is_loaded_and_environment_takes_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            (config / ".env").write_text("CAMERA_RTSP_URL=rtsp://config.invalid/stream1\n", encoding="utf-8")
            with patch("edge.config.settings.CONFIG_DIR", config), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(load_settings().rtsp_url, "rtsp://config.invalid/stream1")
                os.environ["CAMERA_RTSP_URL"] = "rtsp://environment.invalid/stream1"
                self.assertEqual(load_settings().rtsp_url, "rtsp://environment.invalid/stream1")

    # Celá hlavní smyčka vytvoří testovací profil a uklidí zdroje po Q i odpojení.
    def test_loop_uses_real_profile_store_then_cleans_up_on_q_or_disconnect(self):
        for disconnect in (False, True):
            with self.subTest(disconnect=disconnect), tempfile.TemporaryDirectory() as directory:
                settings = Settings(rtsp_url="rtsp://unused.invalid/stream", data_dir=Path(directory),
                                    embedding_size=3, process_interval=0, recognition_interval=0)
                frame = np.full((112, 112, 3), 128, dtype=np.uint8)
                candidate = FaceCandidate(frame, (0, 0, 112, 112),
                                          {"score": 0.8, "usable": True, "view": "front",
                                           "fingerprint": "0000000000000000"}, [1.0, 0.0, 0.0])
                source, processor, gui = MagicMock(), MagicMock(), MagicMock()
                source.read.side_effect = [frame] * 4 + [StreamError("Odpojeno")]
                source.reported_fps = 25.0
                observation = FaceObservation(frame, candidate.box, 0.99, {}, candidate.quality)
                processor.detect.side_effect = [[], [observation], [observation], [observation]]
                processor.evaluate.return_value = candidate.quality
                processor.embed.return_value = candidate
                gui.waitKey.side_effect = [0, 0, 0, 0 if disconnect else ord("q")]

                # Jednoduchá náhrada workeru: místo vlákna provádí výpočet přímo při submit.
                # Tento test pak nezávisí na načasování vláken.
                class InlineWorker:
                    # Uloží testovanou pipeline pro další volání.
                    def __init__(self, pipeline, settings):
                        self.pipeline = pipeline
                    # Tato náhrada nespouští vlákno, proto není co zahajovat.
                    def start(self):
                        pass
                    # Provede skutečnou pipeline synchronně, tedy hned v tomto vlákně.
                    def submit(self, frame, now, timestamp):
                        self.pipeline.process(frame, now, timestamp)
                    # Vrací prázdné popisky a žádnou chybu; test se soustředí na profil a úklid.
                    def snapshot(self):
                        return [], 0, None
                    # Není spuštěné vlákno, proto není na co čekat.
                    def close(self):
                        pass
                gui.getWindowProperty.return_value = 1
                with patch.object(application, "load_settings", return_value=settings), \
                     patch.object(application, "RTSPSource", return_value=source), \
                     patch.object(application, "FaceProcessor", return_value=processor), \
                     patch.object(application, "LiveWorker", InlineWorker), \
                     patch.object(application, "cv2", gui):
                    self.assertEqual(application.main(), int(disconnect))
                source.close.assert_called_once()
                gui.destroyAllWindows.assert_called_once()
                store = ProfileStore(settings)
                self.assertEqual(len(store.profiles), 1)

    # Bez platné konfigurace aplikace skončí s chybou ještě před připojením kamery.
    def test_missing_configuration_is_clean_and_does_not_open_camera(self):
        with patch.object(application, "load_settings", side_effect=SettingsError("Chybi URL")), \
             patch.object(application, "RTSPSource") as source, \
             patch.object(application, "cv2"):
            self.assertEqual(application.main(), 1)
            source.assert_not_called()

    # Výřezy zůstanou v obraze a příliš malé či neplatné nálezy nedostanou embedding.
    def test_face_processor_clamps_boxes_and_skips_poor_crops(self):
        # __new__ vytvoří objekt bez __init__, takže test nenačítá těžké skutečné modely.
        processor = FaceProcessor.__new__(FaceProcessor)
        processor.detector = MagicMock()
        processor.deepface = MagicMock()
        processor.model_name = "Facenet512"
        processor.detection_width = 960
        processor.detector.detect_faces.return_value = [
            {"box": np.array([-20, -20, 132, 132]), "confidence": np.float32(0.99)},
            {"box": (300, 300, 20, 20), "confidence": 0.99},
            {"box": (0, 0, 10, 10), "confidence": 0.99},
        ]
        processor.deepface.represent.return_value = [{"embedding": [1.0, 0.0, 0.0]}]
        frame = np.random.default_rng(7).integers(50, 200, (112, 112, 3), dtype=np.uint8)
        candidates = list(processor.process(frame))
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].box, (0, 0, 112, 112))
        self.assertTrue(all(type(value) is int for value in candidates[0].box))
        self.assertIs(type(candidates[0].quality["score"]), float)
        self.assertIs(type(candidates[0].quality["usable"]), bool)
        processor.deepface.represent.assert_called_once()


# Při přímém spuštění tohoto souboru unittest vyhledá a provede jeho testy.
if __name__ == "__main__":
    unittest.main()
