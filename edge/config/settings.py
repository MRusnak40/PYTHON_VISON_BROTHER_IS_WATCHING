# NASTAVENÍ APLIKACE.
# Settings je společný přehled hodnot předávaných jednotlivým modulům.
# Citlivá adresa kamery se načítá z prostředí nebo místního config/.env.

"""Místní nastavení EDGE; přihlašovací údaje kamery patří do config/.env."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


# Cesty odvodíme od souboru, aby nezávisely na složce otevřené v terminálu.
EDGE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = Path(__file__).resolve().parent


# Vlastní typ chyby pro neplatnou konfiguraci.
class SettingsError(ValueError):
    pass


# dataclass vytvoří objekt s těmito položkami a výchozími hodnotami.
# frozen=True brání běžnému přepisování položek za běhu; typy za dvojtečkou jsou nápověda.
@dataclass(frozen=True)
class Settings:
    """Jeden neměnný balíček nastavení; časové intervaly jsou v sekundách."""

    # ==================== ZDROJ A NAČASOVÁNÍ ====================
    # Síťová adresa streamu; str je text, bool ano/ne, float desetinné číslo a int celé číslo.
    rtsp_url: str
    # Kořen místních dat: JSON ve storage/ a fotky v profiles/.
    data_dir: Path = EDGE_DIR
    # Pauza v sekundách po dokončení zpracování; nezaručuje konkrétní FPS.
    process_interval: float = 0.25
    # Nejmenší rozestup pokusů o identifikaci neznámého tracku.
    recognition_interval: float = 0.4
    # Interval kontrol kvality dalších vzorků známého tracku.
    quality_interval: float = 0.75
    # Největší šířka pro detektor; výřezy zůstávají z originálu.
    detection_width: int = 960
    # Největší šířka náhledu v pixelech.
    preview_width: int = 960
    # ==================== TRACKING A POTVRZENÍ IDENTITY ====================
    # Zachování tracku od první chybějící detekce. Jeho zánik neprokazuje odchod člověka.
    track_timeout: float = 1.5
    # Minimální překryv rámečků pro možné propojení mezi snímky.
    track_iou: float = 0.20
    # Příliš podobné překryvy více kandidátů znamenají nejasné prostorové přiřazení.
    track_margin: float = 0.10
    # Počet kvalitních konzistentních pozorování před pokusem založit osobu.
    identity_observations: int = 3
    # Počet jasných shod se stejným profilem pro potvrzení identity.
    match_observations: int = 2
    # Přísnější práh kvality pro rozhodnutí o identitě.
    identity_quality: float = 0.65
    # Interval výpisu statistik v sekundách.
    metrics_interval: float = 5.0
    # ==================== MODEL A MATCHING ====================
    # Model převádějící obličej na embedding, tedy vektor pro porovnávání.
    model_name: str = "Facenet512"
    # Počet čísel v jednom embeddingu použitého modelu.
    embedding_size: int = 512
    # Nejvyšší přijatelná vzdálenost vektorů: menší znamená podobnější.
    # Nejde o pravděpodobnost nebo procento jistoty.
    match_distance: float = 0.30
    # Nejlepší dva profily musí mít dostatečně odlišné vzdálenosti.
    match_margin: float = 0.05
    # ==================== VÝBĚR VZORKŮ A ZÁPIS ====================
    # Nejvyšší počet uložených fotek jedné osoby.
    max_samples: int = 5
    # Nejvýše dva doplňky ke třem hlavním pohledům left/front/right.
    extra_samples: int = 2
    # Požadované zlepšení skóre pro výměnu obsazeného pohledu.
    quality_improvement: float = 0.05
    # Minimální rozestup mezi uloženými fotkami jedné osoby.
    sample_interval: float = 2.0
    # Interval zápisu změněných časů pozorování do JSON.
    flush_interval: float = 5.0


# Načte .env a ověří nastavení. Již existující proměnné prostředí mají přednost.
def load_settings():
    """Načte místní .env/prostředí → jeden Settings, při neplatné hodnotě SettingsError."""
    # interpolate=False ponechá znaky v hodnotách doslova bez rozbalování odkazů na proměnné.
    load_dotenv(CONFIG_DIR / ".env", interpolate=False)
    url = os.environ.get("CAMERA_RTSP_URL", "").strip()  # Citlivý text streamu po odstranění okrajových mezer.
    try:
        # Rozdělíme URL a zkontrolujeme protokol, hostitele a syntaxi portu.
        address = urlsplit(url)  # Jednotlivé části URL pro validaci; nezakládá spojení.
        if address.scheme not in ("rtsp", "rtsps") or not address.hostname:
            raise ValueError
        _ = address.port  # Samotné načtení vlastnosti prověří platnost portu; hodnotu nepotřebujeme.
    except ValueError:
        raise SettingsError("Nastav platnou CAMERA_RTSP_URL v edge/config/.env nebo v prostredi.") from None

    # setdefault nastavuje jen chybějící hodnotu. sys.prefix ukazuje na Python prostředí s cache modelu.
    os.environ.setdefault("DEEPFACE_HOME", sys.prefix)
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    return Settings(rtsp_url=url)
