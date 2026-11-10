# ZPRACOVÁNÍ OBRAZU NA POZADÍ.
# Vlákno je souběžná větev programu: zde počítá modely, main.py zatím obsluhuje okno.
# Čeká pouze jeden snímek; novější jej přepíše, aby nerostla fronta starého obrazu.

"""Jedno výpočetní vlákno a jediný přepisovaný čekající snímek."""

from threading import Condition, Thread
from time import monotonic
from typing import NamedTuple


class WorkerSnapshot(NamedTuple):
    """Jeden snímek stavu výpočtu; zachovává původní rozbalení trojice."""

    labels: list  # [(box, text)] pro vykreslení v hlavním vlákně.
    published_at: float  # Monotonic čas zpracovaného vstupu; 0 před prvním výsledkem.
    error: Exception | None  # Zachycené selhání workeru, nebo None.


# Obaluje pipeline vláknem a bezpečným předáváním snímků i výsledků.
class LiveWorker:
    # ==================== SDÍLENÝ STAV A VEŘEJNÉ METODY ====================
    # Připraví sdílený stav; vlákno zatím nespustí.
    def __init__(self, pipeline, settings):
        self.pipeline = pipeline  # VisionPipeline: vlastní výpočty a změny profilů.
        self.settings = settings  # Settings: pauza mezi výpočty a výpisy metrik.
        # Zámek chrání společné proměnné před současnou úpravou z různých vláken.
        self.condition = Condition()
        self.pending = None  # Čekající (frame, observed_at, timestamp), nebo prázdný slot.
        self.labels = []  # Poslední dokončené obdélníky/popisky.
        self.published_at = 0.0  # Monotonic čas snímku, ke kterému patří labels.
        self.error = None  # Výjimka k předání hlavnímu vláknu.
        self.stopped = False  # Žádost o ukončení, chráněná condition.
        self.thread = None  # Objekt Thread; vznikne až při start().
        self.dropped = 0  # Celkový počet přepsaných čekajících vstupů.

    # Spustí metodu _run na pozadí.
    def start(self):
        """Spustí _run() na pozadí; vrací None."""
        self.thread = Thread(target=self._run, name="vision-worker", daemon=True)
        self.thread.start()

    # Předá snímek z hlavní smyčky bez čekání na dokončení výpočtu.
    def submit(self, frame, observed_at, timestamp):
        """BGR pixely + datum UTC + monotonic čas → předání práce, návrat None."""
        # frame se nekopíruje; volající do originálu nesmí kreslit.
        with self.condition:
            # Pokud výpočet nestíhá, přeskočíme starší čekající snímek a zvýšíme čítač.
            if self.pending is not None:
                self.dropped += 1
            self.pending = (frame, observed_at, timestamp)
            self.condition.notify_all()

    # Vrátí poslední popisky, čas jejich snímku a případnou chybu.
    def snapshot(self) -> WorkerSnapshot:
        """Vrátí jeden WorkerSnapshot bez čekání na dokončení inference."""
        with self.condition:
            # Kopie seznamu brání tomu, aby hlavní vlákno přímo upravovalo interní seznam popisků.
            return WorkerSnapshot(list(self.labels), self.published_at, self.error)

    # ==================== ČEKÁNÍ NA JEDINÝ NEJNOVĚJŠÍ VSTUP ====================

    def _take_pending(self, next_process):
        """Počká na povolený výpočet; vrátí vstupní trojici, při zastavení None."""
        with self.condition:
            while True:
                # wait_for při čekání uvolňuje zámek; submit() může přepisovat slot.
                self.condition.wait_for(lambda: self.stopped or self.pending is not None)
                if self.stopped:
                    return None
                remaining = next_process - monotonic()  # Zbytek povinné pauzy v sekundách.
                if remaining > 0:
                    self.condition.wait(timeout=remaining)
                    continue
                pending = self.pending  # Právě nejnovější (frame, observed_at, timestamp).
                self.pending = None
                return pending

    # ==================== VÝPOČETNÍ VLÁKNO ====================
    # Čeká na práci, dodržuje pauzy mezi výpočty a předává hotové výsledky.
    def _run(self):
        """Řídí výpočty a publikuje výsledky; při chybě ji uloží do snapshot()."""
        next_process = 0.0  # Nejbližší povolený začátek dalšího výpočtu (monotonic).
        last_report = monotonic()  # Začátek intervalu metrik.
        previous = dict(self.pipeline.stats)  # Kopie kumulativních čítačů při minulém výpisu.
        try:
            # DŮLEŽITÁ SMYČKA C: výpočetní vlákno; jeden vstup = jeden process().
            while True:
                pending = self._take_pending(next_process)
                if pending is None:
                    return
                frame, observed_at, timestamp = pending
                # frame = originál BGR; observed_at = UTC datum; timestamp = monotonic čas vstupu.
                # Počítáme mimo zámek, aby hlavní smyčka mohla předávat další snímek.
                labels, events = self.pipeline.process(frame, observed_at, timestamp)
                finished = monotonic()  # Čas dokončení; od něj počítáme povinnou pauzu.
                with self.condition:
                    # Ukládáme čas původního snímku; náhled podle něj pozná zastaralé rámečky.
                    self.labels, self.published_at = labels, timestamp
                for event in events:
                    # event je jedna změna profilu/identity, nikoli každý přijatý snímek.
                    print(f"T{event['track_id']} -> {event.get('person_id', '?')}: {event['status']}", flush=True)
                next_process = finished + self.settings.process_interval
                if finished - last_report >= self.settings.metrics_interval:
                    previous = self._report_metrics(previous, finished - last_report)
                    last_report = finished
        except Exception as error:
            with self.condition:
                # Výjimka z vedlejšího vlákna se do hlavního sama nepřenese, proto ji zde uložíme.
                self.error = error

    # ==================== METRIKY A UKONČENÍ ====================

    def _report_metrics(self, previous, seconds) -> dict:
        """Vypíše metriky za uplynulé sekundy a vrátí novou kopii čítačů."""
        current = self.pipeline.stats  # Celkové počty a časy od startu pipeline.
        delta = {key: current[key] - previous[key] for key in current}  # Přírůstky za interval.
        # Průměrné doby v ms na volání; max chrání před nulovým počtem volání.
        average = 1000 * delta["embedding_seconds"] / max(1, delta["embeddings"])
        detection = 1000 * delta["detection_seconds"] / max(1, delta["frames"])
        print(f"Vision: {delta['frames'] / seconds:.1f} sn/s; "
              f"embeddingy: {delta['embeddings'] / seconds:.2f}/s ({average:.0f} ms/call); "
              f"matching: {delta['matches'] / seconds:.2f}/s; "
              f"detekce: {detection:.0f} ms/call; preskocene snimky: {self.dropped}", flush=True)
        return dict(current)

    # Požádá o konec a počká na běžící výpočet; čekající snímek už nezpracuje.
    def close(self):
        """Zahodí čekající vstup a počká na rozpracovaný; vrací None."""
        with self.condition:
            self.stopped = True
            self.pending = None
            self.condition.notify_all()
        if self.thread is not None:
            # Počkáme na konec výpočtu před posledním uložením profilů v main.py.
            self.thread.join()
