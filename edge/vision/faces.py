# DETEKCE OBLIČEJŮ A VÝPOČET EMBEDDINGŮ.
# Detekce odpovídá „kde je obličej“. Embedding je vektor čísel pro porovnávání tváří.
# Modul dostává snímky, takže sám nepotřebuje znát RTSP ani výrobce kamery.

"""Společné zpracování libovolného BGR snímku, nezávislé na zdroji obrazu."""

from dataclasses import dataclass

import cv2
import numpy as np

from .quality import evaluate_face


# Datový balíček hotového kandidáta: výřez, rámeček, kvalita a embedding.
@dataclass
class FaceCandidate:
    crop: np.ndarray  # Kopie pixelů obličeje, BGR, [výška, šířka, 3].
    box: tuple  # (x, y, šířka, výška) v původním snímku.
    quality: dict  # score/usable/view/fingerprint a další metadata z quality.py.
    embedding: list  # Seznam 512 Python floatů pro Facenet512; ukládá se do JSON.


# Detekce před výpočtem embeddingu; quality může být zatím None.
# crop je pole pixelů, box je (x, y, šířka, výška), keypoints jsou například oči a nos.
@dataclass
class FaceObservation:
    crop: np.ndarray  # Výřez původního obrazu, nikoli zmenšený vstup detektoru.
    box: tuple  # (x, y, šířka, výška) v původních pixelech.
    confidence: float  # Výstup detektoru MTCNN; není jistotou identity.
    keypoints: dict  # Jméno bodu (např. nose) → (x, y) v původním snímku.
    quality: dict | None = None  # Cache hodnocení; None = ještě nespočítáno.


# Nabízí odděleně detekci, hodnocení kvality a výpočet embeddingu.
class FaceProcessor:
    # ==================== JEDNORÁZOVÉ NAČTENÍ MODELŮ ====================
    # Drahé modely načteme jednou při spuštění, nikoli znovu pro každý snímek.
    def __init__(self, settings):
        # Importy a načtení vah se provádějí až při vytvoření procesoru.
        from mtcnn import MTCNN
        from deepface import DeepFace

        self.detector = MTCNN()  # Model hledající boxy a body tváře.
        self.deepface = DeepFace  # API pro výpočet embeddingu.
        self.model_name = settings.model_name  # Název modelu shodný s uloženými profily.
        self.detection_width = settings.detection_width  # Limit šířky vstupu MTCNN v pixelech.
        DeepFace.build_model(self.model_name)

    # ==================== DETEKCE A VÝŘEZY ====================

    # Najde obličeje na případně zmenšeném obraze, výřezy vezme z originálu.
    # yield předává jednotlivé nálezy postupně, místo vytváření celého seznamu najednou.
    def detect(self, frame):
        """BGR snímek → generátor FaceObservation; zatím bez embeddingů."""
        # shape vrací rozměry pole; [:2] vybere výšku a šířku bez počtu barevných složek.
        height, width = frame.shape[:2]
        small_width = min(width, self.detection_width)
        small_height = max(1, round(height * small_width / width))
        small = cv2.resize(frame, (small_width, small_height)) if small_width < width else frame
        # OpenCV používá pořadí barev BGR, MTCNN očekává RGB, proto barvy převedeme.
        detections = self.detector.detect_faces(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        # detections = seznam slovníků MTCNN: box, confidence, keypoints.
        # Souřadnice z detektoru násobením vrátíme do rozměrů původního snímku.
        scale_x, scale_y = width / small_width, height / small_height
        # Každou detekci převedeme do původního měřítka a vyřízneme samostatně.
        for face in detections:
            observation = self._extract_observation(face, frame, scale_x, scale_y)
            if observation is not None:
                yield observation

    def _extract_observation(self, face, frame, scale_x, scale_y):
        """Detekce MTCNN → výřez a metadata v měřítku originálu, nebo None mimo obraz."""
        height, width = frame.shape[:2]  # Hranice originálu v pixelech.
        x, y, w, h = face["box"]  # Levý horní roh a rozměry ve vstupu detektoru.
        x, y, right, bottom = (int(np.floor(x * scale_x)), int(np.floor(y * scale_y)),
                              int(np.ceil((x + w) * scale_x)), int(np.ceil((y + h) * scale_y)))
        x1, y1 = max(0, x), max(0, y)  # Levý horní roh omezený hranicemi snímku.
        x2, y2 = min(width, right), min(height, bottom)  # Pravý dolní roh (nezahrnutý ve výřezu).
        if x2 <= x1 or y2 <= y1:
            return None
        crop = frame[y1:y2, x1:x2].copy()  # Vlastní pixely; indexujeme řádek y, pak sloupec x.
        keypoints = {name: (float(point[0] * scale_x), float(point[1] * scale_y))
                     for name, point in face.get("keypoints", {}).items()}
        # name = jméno bodu, point = (x, y) detektoru; přepočet odpovídá boxu.
        return FaceObservation(crop, (x1, y1, x2 - x1, y2 - y1), float(face["confidence"]), keypoints)

    # ==================== KVALITA A EMBEDDING ====================

    # Kvalitu spočítá při prvním požadavku a uloží ji do pozorování pro další použití.
    def evaluate(self, observation):
        """Vrátí slovník kvality; opakované volání používá cache pozorování."""
        if observation.quality is None:
            observation.quality = evaluate_face(observation.crop, observation.confidence, observation.keypoints)
        return observation.quality

    # Převede výřez na vektor; vadný výsledek odmítne vrácením None.
    def embed(self, observation):
        """Jedno pozorování → FaceCandidate s embeddingem, nebo None při vadném vektoru."""
        # detector_backend="skip": obličej je již vyříznutý, detekci neopakujeme.
        # normalization="base" musí odpovídat nastavení uložených embeddingů.
        result = self.deepface.represent(
            img_path=observation.crop, model_name=self.model_name,
            detector_backend="skip", enforce_detection=False, align=False, normalization="base",
        )
        # result je seznam odpovědí DeepFace; první odpovídá našemu jedinému výřezu.
        embedding = np.asarray(result[0]["embedding"], dtype=float)  # NumPy vektor pro validaci.
        # NaN, nekonečna nebo nulový vektor by znemožnily smysluplné porovnání.
        if not np.isfinite(embedding).all() or np.linalg.norm(embedding) == 0:
            return None
        return FaceCandidate(observation.crop, observation.box, self.evaluate(observation), embedding.tolist())

    # Souhrnná varianta pro detekci, kontrolu kvality a embeddingy.
    # Živá pipeline používá kroky odděleně, aby nepočítala zbytečné embeddingy.
    def process(self, frame):
        """BGR snímek → generátor použitelných FaceCandidate; synchronní pomocné API."""
        for observation in self.detect(frame):
            if self.evaluate(observation)["usable"]:
                candidate = self.embed(observation)
                if candidate is not None:
                    yield candidate
