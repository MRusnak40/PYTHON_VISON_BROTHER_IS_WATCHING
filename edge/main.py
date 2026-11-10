"""Vstup EDGE: spuštění → příprava → hlavní smyčka → úklid.

Spuštění: python -X utf8 edge/main.py (v prostředí edge/.venv).
Mapa volání a proměnných: docs/EDGE_CODE_GUIDE.md.
Importované soubory nejsou samostatné procesy: používáme jejich třídy/metody.
"""

from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from traceback import extract_tb

# Dvě varianty importu podporují přímé spuštění i python -m edge.main.
# Import sám neotevírá kameru ani nenačítá modely.
if __package__:
    from .cameras.source import RTSPSource, StreamError, cv2
    from .config.settings import SettingsError, load_settings
    from .vision.faces import FaceProcessor
    from .vision.profiles import ProfileDataError, ProfileStore
    from .vision.pipeline import VisionPipeline
    from .vision.live import LiveWorker
else:
    from cameras.source import RTSPSource, StreamError, cv2
    from config.settings import SettingsError, load_settings
    from vision.faces import FaceProcessor
    from vision.profiles import ProfileDataError, ProfileStore
    from vision.pipeline import VisionPipeline
    from vision.live import LiveWorker


WINDOW = "EDGE - Q / Esc: konec"  # Jméno okna používané všemi OpenCV voláními.


def report_runtime_error(error, stage):
    """Vypíše typ a místo chyby v dané fázi; vrací None, ne text výjimky s tajemstvími."""
    root = Path(__file__).resolve().parent  # Absolutní cesta k edge/.
    location = "nezname misto"  # Náhradní popis, pokud traceback nemá aplikační řádek.
    # Projdeme zásobník volání; ponecháme poslední místo uvnitř našeho kódu.
    for frame in extract_tb(error.__traceback__):
        path = Path(frame.filename).resolve()  # Soubor jednoho záznamu tracebacku.
        if path.is_relative_to(root) and ".venv" not in path.parts:
            location = f"{path.relative_to(root).as_posix()}:{frame.lineno}"
    print(f"EDGE chyba pri {stage}: {type(error).__name__} ({location}).", flush=True)


class EdgeApplication:
    """Řídí život aplikace; čtení kamery a výpočty deleguje existujícím třídám.

    Každé run() patří nový objekt. Metody s příkazy vracejí None;
    metody s dotazem vracejí jeden výsledek. Stav zdrojů je uložený v self.
    """

    # ==================== 1. STAV A ŘÍZENÍ BĚHU ====================

    def __init__(self):
        """Připraví prázdný stav; zatím nic nepřipojuje ani nespouští."""
        self.settings = None  # Settings: konfigurace společná pro tento běh.
        self.store = None  # ProfileStore: lokální osoby, vzorky a zápis JSON.
        self.worker = None  # LiveWorker: vlákno volající vision pipeline.
        self.source = None  # RTSPSource: síťové video a jeho čtecí vlákno.
        self.exit_code = 0  # Jediný konečný výsledek run(): 0 = úspěch, 1 = chyba.
        self.stage = "nacitani konfigurace"  # Poslední fáze pro bezpečné hlášení chyby.

    def run(self) -> int:
        """Provede životní cyklus a vrátí návratový kód procesu (0 nebo 1)."""
        try:
            self._prepare_vision()
            self._open_camera()
            self._open_preview()
            self._preview_loop()
        except KeyboardInterrupt:
            print("Ukoncuji EDGE...")
        except (SettingsError, ProfileDataError, StreamError) as error:
            # Tyto aplikační výjimky mají vlastní zprávy bez citlivých údajů.
            print(str(error))
            self.exit_code = 1
        except Exception as error:
            report_runtime_error(error, self.stage)
            self.exit_code = 1
        finally:
            # Úklid proběhne také po chybě uprostřed přípravy.
            self._shutdown()
        return self.exit_code

    # ==================== 2. JEDNORÁZOVÁ PŘÍPRAVA ====================

    def _prepare_vision(self) -> None:
        """Načte konfiguraci, profily a modely; připraví dosud neběžící worker."""
        self.settings = load_settings()
        self.stage = "nacitani profilu"
        self.store = ProfileStore(self.settings)
        print(f"Nacteno profilu: {len(self.store.profiles)}. Nacitam modely...", flush=True)
        self.stage = "nacitani modelu"
        processor = FaceProcessor(self.settings)  # Jediná instance MTCNN a Facenet512.
        pipeline = VisionPipeline(processor, self.store, self.settings)  # Postup pro jeden snímek.
        self.worker = LiveWorker(pipeline, self.settings)

    def _open_camera(self) -> None:
        """Po přípravě modelů otevře obecný RTSP stream z nakonfigurované URL."""
        self.stage = "otevirani RTSP spojeni"
        self.source = RTSPSource(self.settings.rtsp_url)
        self.source.open()  # Spouští RTSPSource._receive() v čtecím vlákně.
        print(f"Kamera hlasi FPS: {self.source.reported_fps:.1f}", flush=True)

    def _open_preview(self) -> None:
        """Otevře GUI a spustí výpočetní vlákno; zůstáváme v hlavním vlákně."""
        self.stage = "priprave nahledu"
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW, 960, 540)
        self.worker.start()  # Spouští LiveWorker._run(), který čeká na submit().
        print("EDGE bezi. Q, Esc, zavreni okna nebo Ctrl+C ukonci zpracovani.", flush=True)

    # ==================== 3. HLAVNÍ SMYČKA: NÁHLED A VSTUP ====================

    def _preview_loop(self) -> None:
        """Opakuje příjem → předání výpočtu → náhled → klávesnice až do ukončení."""
        last_report = monotonic()  # Začátek intervalu měření náhledu, sekundy.
        preview_frames = 0  # Počet zobrazených snímků od posledního výpisu.
        # DŮLEŽITÁ SMYČKA A: běží v hlavním vlákně; zde se nepočítají modely.
        while True:
            self.stage = "cteni RTSP snimku"
            frame = self.source.read()  # ndarray [výška, šířka, 3], původní BGR pixely.
            timestamp = monotonic()  # Relativní čas pro intervaly, nikoli datum do JSON.
            self.worker.submit(frame, datetime.now(timezone.utc), timestamp)
            self.stage = "zpracovani vision"
            labels, published_at, error = self.worker.snapshot()
            # labels: [(box, text)]; published_at: monotonic čas jejich snímku;
            # error: výjimka z výpočetního vlákna, nebo None.
            if error is not None:
                raise error
            self.stage = "vykreslovani nahledu"
            self._show_preview(frame, labels, published_at, timestamp)
            preview_frames += 1
            if self._handle_input():
                break
            if timestamp - last_report >= self.settings.metrics_interval:
                print(f"Nahled: {preview_frames / (timestamp - last_report):.1f} sn/s", flush=True)
                last_report, preview_frames = timestamp, 0

    def _show_preview(self, frame, labels, published_at, timestamp) -> None:
        """Zobrazí zmenšenou kopii s čerstvými popisky; původní pixely nemění."""
        height, width = frame.shape[:2]  # Rozměry původního obrazu v pixelech.
        display_width = min(width, self.settings.preview_width)
        display_height = max(1, round(height * display_width / width))
        display = cv2.resize(frame, (display_width, display_height))  # Samostatný obraz pro GUI.
        scale_x = display_width / width  # Přepočet vodorovných souřadnic originál → náhled.
        scale_y = display_height / height  # Přepočet svislých souřadnic.
        if timestamp - published_at <= self.settings.track_timeout:
            # Jeden průchod pro každý hotový popisek, nikoli nový výpočet identity.
            for (x, y, w, h), label in labels:
                # box = levý horní roh x/y a šířka/výška w/h; label = text tracku/osoby.
                x, y, w, h = int(x * scale_x), int(y * scale_y), int(w * scale_x), int(h * scale_y)
                cv2.rectangle(display, (x, y), (x + w, y + h), (0, 220, 0), 2)
                cv2.putText(display, label, (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 220, 0), 2)
        cv2.imshow(WINDOW, display)

    def _handle_input(self) -> bool:
        """Obslouží okno; vrátí True pouze při žádosti o konec aplikace."""
        key = cv2.waitKey(1) & 0xFF  # Číselný kód klávesy; 27 = Escape.
        if key in (ord("q"), ord("Q"), 27):
            return True
        if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
            return True
        return False

    # ==================== 4. ÚKLID: POŘADÍ JE DŮLEŽITÉ ====================

    def _shutdown(self) -> None:
        """Zavře video → dokončí výpočet → uloží časy → zavře GUI."""
        self._close_source()
        self._close_worker()
        self._flush_store()
        cv2.destroyAllWindows()

    def _close_source(self) -> None:
        """Zastaví příjem streamu; jeho chyba nevynechá následující uložení."""
        if self.source is not None:
            try:
                self.source.close()
            except Exception:
                print("RTSP spojeni se nepodarilo korektne uzavrit.")
                self.exit_code = 1

    def _close_worker(self) -> None:
        """Počká na rozpracovaný výpočet, aby už nikdo neměnil profily při flush()."""
        if self.worker is not None:
            self.worker.close()
            _, _, error = self.worker.snapshot()  # Popisky při ukončování nepotřebujeme.
            if error is not None and not self.exit_code:
                report_runtime_error(error, "zpracovani vision")
                self.exit_code = 1

    def _flush_store(self) -> None:
        """Vynutí poslední zápis změněných časů; vrací None."""
        if self.store is not None:
            try:
                self.store.flush(datetime.now(timezone.utc), force=True)
            except Exception:
                print("Posledni casy pozorovani se nepodarilo ulozit do profiles.json.")
                self.exit_code = 1


def main() -> int:
    """Vytvoří aplikaci pro jeden běh a vrátí její návratový kód."""
    return EdgeApplication().run()


# Při importu z testů se neprovede. SystemExit předá návratový kód operačnímu systému.
if __name__ == "__main__":
    raise SystemExit(main())
