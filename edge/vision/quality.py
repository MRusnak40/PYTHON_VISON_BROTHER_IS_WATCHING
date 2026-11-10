# VÝBĚR POUŽITELNÝCH FOTEK OBLIČEJE.
# Jednoduchá pravidla hodnotí velikost, ostrost, jas a rozmanitost vzorků.
# Skóre není kalibrované měření ani pravděpodobnost správné identity.

"""Jednoduchá pravidla kvality výřezu; prahy nejsou kalibrovaný model."""

import cv2


# Vrátí slovník s kvalitou výřezu, použitelností, otiskem fotky a odhadem pohledu.
def evaluate_face(crop, confidence, keypoints):
    """BGR výřez + confidence detektoru + body tváře → jeden slovník metadat kvality.

    score = heuristická kvalita 0–1, usable = splnění všech prahů,
    width/height = původní pixely, sharpness = rozptyl Laplaciánu,
    confidence = výstup MTCNN, view = hrubý pohled, fingerprint = dHash fotografie.
    """
    # Převedeme typ NumPy na běžný Python float, který lze zapsat do JSON.
    confidence = float(confidence)
    height, width = crop.shape[:2]  # Původní výška a šířka výřezu v pixelech.
    # Pro ostrost a jas nepotřebujeme barvy, použijeme odstíny šedi.
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)  # Jednokanálový obraz jasu.
    # Ostrost porovnáme při stejném rozměru, aby větší výřez automaticky nevyhrál.
    normalized = cv2.resize(gray, (112, 112), interpolation=cv2.INTER_AREA)
    # Laplacián zvýrazní změny jasu; rozptyl jeho hodnot zde slouží jako ukazatel ostrosti.
    sharpness = float(cv2.Laplacian(normalized, cv2.CV_64F).var())
    brightness = float(gray.mean())  # Průměrný jas původního výřezu, 0 až 255.
    # Vážené skóre kombinuje velikost (35 %), ostrost (50 %) a výstup detektoru (15 %).
    # min(..., 1.0) zastropuje příspěvek každé vlastnosti.
    score = (
        0.35 * min(min(width, height) / 224, 1.0)
        + 0.50 * min(sharpness / 400, 1.0)
        + 0.15 * confidence
    )
    # Musí současně platit všechny podmínky, samotné celkové skóre nestačí.
    usable = (
        min(width, height) >= 80 and confidence >= 0.95
        and sharpness >= 60 and 30 <= brightness <= 225 and score >= 0.50
    )

    return {
        "score": round(score, 4), "usable": usable,
        "width": width, "height": height,
        "sharpness": round(sharpness, 2), "confidence": float(confidence),
        "view": estimate_view(keypoints), "fingerprint": image_fingerprint(gray),
    }


def estimate_view(keypoints) -> str:
    """Body tváře → left/front/right/unknown; hrubý pohled ve směru obrazu, nikoli úhel."""
    view = "unknown"  # Bez dostatečně vzdálených bodů očí nelze pohled odhadnout.
    if all(name in keypoints for name in ("left_eye", "right_eye", "nose")):
        eye_a, eye_b = keypoints["left_eye"], keypoints["right_eye"]  # Body (x, y) obou očí.
        eye_span = abs(eye_b[0] - eye_a[0])  # Vodorovná vzdálenost očí v pixelech.
        if eye_span > 1:
            # offset = bezrozměrný posun nosu od středu očí, dělený vzdáleností očí.
            offset = (keypoints["nose"][0] - (eye_a[0] + eye_b[0]) / 2) / eye_span
            view = "left" if offset < -0.15 else "right" if offset > 0.15 else "front"
    return view


def image_fingerprint(gray) -> str:
    """Šedý výřez → 16 hex znaků dHash; podobnost fotografií, nikoli identita osoby."""
    # Z malého obrazu vytvoříme 64bitový otisk porovnáním sousedních pixelů.
    # Hledá podobné fotky; není to embedding pro rozpoznávání člověka.
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)  # 8 řádků po 9 pixelech.
    fingerprint = 0  # Celé číslo, do kterého postupně přidáme 64 porovnání.
    # DŮLEŽITÁ SMYČKA: 8 × 8 porovnání sousedů → 64 bitů otisku.
    for bit in (small[:, 1:] > small[:, :-1]).flat:
        # Každé porovnání přidá jeden bit; výsledek uložíme jako 16 šestnáctkových znaků.
        fingerprint = (fingerprint << 1) | int(bit)
    return f"{fingerprint:016x}"
