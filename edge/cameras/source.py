# PŘÍJEM VIDEA Z RTSP KAMERY.
# RTSP přenáší obraz po síti; OpenCV jej přes FFmpeg převádí na snímky.
# Tady se řeší pouze příjem, nikoli rozpoznávání nebo ovládání kamery.

"""Příjem RTSP videa; připojení streamu, čtecí vlákno a předávání BGR snímků."""

import os
from threading import Condition, Thread

# Diagnostiku nastavujeme před importem cv2, aby nevypsala přihlašovací údaje z URL.
for name, value in {
    "OPENCV_LOG_LEVEL": "SILENT",
    "OPENCV_VIDEOIO_DEBUG": "0",
    "OPENCV_VIDEOCAPTURE_DEBUG": "0",
    "OPENCV_FFMPEG_DEBUG": "0",
    "OPENCV_FFMPEG_LOGLEVEL": "-8",
}.items():
    # name = jméno proměnné prostředí; value = hodnota potlačující citlivé logy knihoven.
    os.environ[name] = value

import cv2


# Srozumitelná chyba při otevírání nebo čtení streamu.
class StreamError(RuntimeError):
    pass


# Zdroj s vlastním čtecím vláknem a místem pouze pro nejnovější snímek.
class RTSPSource:
    # ==================== STAV A OTEVŘENÍ STREAMU ====================
    # Připraví stav objektu; spojení se otevře až metodou open.
    def __init__(self, url):
        self.url = url  # Citlivá adresa RTSP; nevypisovat do terminálu.
        self.capture = None  # OpenCV VideoCapture / FFmpeg spojení.
        # Condition je zámek s čekáním a probouzením; chrání společný stav různých vláken.
        self.condition = Condition()
        self.thread = None  # Čtecí Thread vytvořený v open().
        self.stopped = False  # Požadavek hlavního vlákna ukončit příjem.
        self.failed = False  # Čtečka skončila nebo selhala; read() ohlásí StreamError.
        self.frame = None  # Jediný nejnovější BGR snímek; None = zatím není nepřevzatý vstup.
        self.reported_fps = 0.0  # FPS nahlášené kamerou; nejde o změřený výkon aplikace.

    # Otevře stream, nastaví časové limity a spustí čtecí vlákno.
    def open(self):
        """Otevře RTSP a spustí _receive() v dalším vlákně; vrací None."""
        self.capture = cv2.VideoCapture()
        try:
            # Timeouty jsou v milisekundách; 10000 znamená 10 sekund.
            self.capture.open(
                self.url,
                cv2.CAP_FFMPEG,
                [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000,
                 cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000],
            )
            if not self.capture.isOpened():
                raise StreamError("RTSP nelze otevrit. Over adresu, ucet a dostupnost kamery.")
            self.reported_fps = float(self.capture.get(cv2.CAP_PROP_FPS))
        except cv2.error:
            raise StreamError("Chyba pri otevirani RTSP spojeni.") from None
        # Thread spouští souběžnou práci. daemon vlákno samo neudržuje program naživu.
        self.thread = Thread(target=self._receive, name="rtsp-reader", daemon=True)
        self.thread.start()

    # ==================== PŘÍJEM NA POZADÍ ====================

    # Na pozadí čte video a novým snímkem přepisuje předchozí čekající snímek.
    def _receive(self):
        """Čte dekódované BGR obrazy do jediného slotu; vrací None při konci příjmu."""
        try:
            # DŮLEŽITÁ SMYČKA B: běží ve vlákně rtsp-reader nezávisle na modelech.
            while not self.stopped:
                success, frame = self.capture.read()  # bool úspěchu a ndarray pixelů, nebo None.
                if not success or frame is None or frame.size == 0:
                    break
                with self.condition:
                    self.frame = frame
                    self.condition.notify_all()
        except Exception:
            # Text výjimky dekodéru může obsahovat citlivou RTSP adresu.
            pass
        finally:
            with self.condition:
                self.failed = True
                self.condition.notify_all()
            self.capture.release()

    # ==================== PŘEDÁNÍ HLAVNÍ SMYČCE A UKONČENÍ ====================

    # Počká na snímek a předá jej volajícímu, typicky hlavní smyčce.
    def read(self):
        """Vrátí jeden nejnovější BGR snímek; při odpojení/timeoutu vyvolá StreamError."""
        with self.condition:
            # Čekání uvolní zámek a skončí po splnění podmínky nebo vypršení limitu.
            ready = self.condition.wait_for(
                lambda: self.frame is not None or self.failed, timeout=12,
            )
            # ready = podmínka byla splněna do 12 s; failed rozlišuje konec čtečky.
            if not ready or self.failed:
                raise StreamError("RTSP neposila snimky nebo bylo spojeni preruseno.")
            # Převezmeme snímek a vyprázdníme slot; další read čeká na další dostupný snímek.
            frame, self.frame = self.frame, None
            return frame

    # Požádá čtecí vlákno o konec a omezenou dobu počká na dokončení.
    def close(self):
        """Požádá čtečku o konec a čeká nejvýše 12 s; vrací None."""
        self.stopped = True
        if self.thread is not None:
            # join čeká na konec vlákna. FFmpeg má vlastní limit čtení, proto je čekání omezené.
            self.thread.join(timeout=12)
        elif self.capture is not None:
            self.capture.release()
