"""Obecný RTSP životní cyklus; kamera, modely i GUI jsou nahrazené, bez síťových příkazů."""

from io import StringIO
from unittest import TestCase
from unittest.mock import ANY, patch

import numpy as np

from edge import main as application
from edge.cameras.source import StreamError
from edge.config.settings import Settings


class ApplicationLifecycleTests(TestCase):
    def setUp(self):
        # Náhrady závislostí oddělují test životního cyklu od modelů a fyzické kamery.
        self.mocks = {}
        for name in ("load_settings", "ProfileStore", "FaceProcessor", "RTSPSource", "LiveWorker", "cv2"):
            self.mocks[name] = self.enterContext(patch.object(application, name))
        self.mocks["load_settings"].return_value = Settings(rtsp_url="rtsp://camera.invalid/live")
        self.source = self.mocks["RTSPSource"].return_value  # Náhrada síťového zdroje.
        self.source.read.return_value = np.zeros((112, 112, 3), dtype=np.uint8)
        self.source.reported_fps = 25.0
        self.worker = self.mocks["LiveWorker"].return_value  # Náhrada výpočetního vlákna.
        self.worker.snapshot.return_value = ([], 0.0, None)
        self.store = self.mocks["ProfileStore"].return_value  # Náhrada lokálních dat.
        self.gui = self.mocks["cv2"]  # Náhrada okna, klávesnice i vykreslování.
        self.gui.waitKey.return_value = ord("q")
        self.gui.getWindowProperty.return_value = 1
        self.events = []  # Pozorované pořadí otevření, spuštění a úklidu.
        self.source.open.side_effect = lambda: self.events.append("rtsp_open")
        self.worker.start.side_effect = lambda: self.events.append("worker_start")
        self.source.close.side_effect = lambda: self.events.append("rtsp_close")
        self.worker.close.side_effect = lambda: self.events.append("worker_close")
        self.store.flush.side_effect = lambda *args, **kwargs: self.events.append("store_flush")
        self.gui.destroyAllWindows.side_effect = lambda: self.events.append("windows_close")

    def test_normal_start_and_shutdown_order(self):
        """Finální flush přichází až po ukončení výpočetního vlákna."""
        self.assertEqual(application.main(), 0)
        self.assertEqual(self.events, ["rtsp_open", "worker_start", "rtsp_close",
                                       "worker_close", "store_flush", "windows_close"])

    def test_termination_signals_and_failures_cleanup_resources(self):
        """Escape, okno, Ctrl+C, odpojení i chyba modelu mají společný úklid."""
        for mode in ("escape", "window", "ctrl_c", "disconnect", "vision_error"):
            with self.subTest(mode=mode):
                self.source.read.side_effect = None
                self.worker.snapshot.return_value = ([], 0.0, None)
                self.gui.waitKey.return_value = 27
                self.gui.getWindowProperty.return_value = 1
                self.events.clear()
                if mode == "window":
                    self.gui.waitKey.return_value = 0
                    self.gui.getWindowProperty.return_value = 0
                elif mode == "ctrl_c":
                    self.source.read.side_effect = KeyboardInterrupt()
                elif mode == "disconnect":
                    self.source.read.side_effect = StreamError("Odpojeno")
                elif mode == "vision_error":
                    self.worker.snapshot.return_value = ([], 0.0, RuntimeError("private error"))
                self.assertEqual(application.main(), int(mode in ("disconnect", "vision_error")))
                self.assertEqual(self.events[-4:], ["rtsp_close", "worker_close", "store_flush", "windows_close"])

    def test_failed_rtsp_open_is_cleaned_up(self):
        """I částečně otevřený zdroj se uzavře; worker se ještě nespouští."""
        self.source.open.side_effect = StreamError("RTSP nelze otevrit")
        self.assertEqual(application.main(), 1)
        self.source.close.assert_called_once()
        self.worker.start.assert_not_called()
        self.store.flush.assert_called_once_with(ANY, force=True)

    def test_source_close_failure_cannot_skip_storage_or_gui_cleanup(self):
        self.source.close.side_effect = RuntimeError("failed close")
        self.assertEqual(application.main(), 1)
        self.worker.close.assert_called_once()
        self.store.flush.assert_called_once_with(ANY, force=True)
        self.gui.destroyAllWindows.assert_called_once()

    def test_model_failure_does_not_open_camera(self):
        self.mocks["FaceProcessor"].side_effect = RuntimeError("missing weights")
        self.assertEqual(application.main(), 1)
        self.mocks["RTSPSource"].assert_not_called()
        self.store.flush.assert_called_once_with(ANY, force=True)

    def test_error_reports_stage_without_secret_exception_message(self):
        self.worker.snapshot.return_value = ([], 0.0, TypeError("rtsp://secret-user:secret-pass@camera.invalid/private"))
        with patch("sys.stdout", new_callable=StringIO) as output:
            self.assertEqual(application.main(), 1)
        self.assertIn("zpracovani vision: TypeError", output.getvalue())
        self.assertIn("main.py:", output.getvalue())
        self.assertNotIn("secret", output.getvalue())

    def test_changing_only_url_changes_stream_source(self):
        """Různé adresy/cesty používají stejnou aplikaci bez dalšího přepínače."""
        for url in ("rtsp://first-camera.invalid:554/live", "rtsp://user:password@second-camera.invalid/video/main"):
            with self.subTest(url=url):
                self.mocks["load_settings"].return_value = Settings(rtsp_url=url)
                self.assertEqual(application.main(), 0)
                self.mocks["RTSPSource"].assert_called_with(url)

    def test_other_keys_do_not_interrupt_preview(self):
        self.gui.waitKey.side_effect = [ord("w"), ord("a"), ord("s"), ord("d"), ord("q")]
        self.assertEqual(application.main(), 0)
        self.assertEqual(self.worker.submit.call_count, 5)
