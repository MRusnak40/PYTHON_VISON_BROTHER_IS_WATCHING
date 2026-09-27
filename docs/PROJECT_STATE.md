# Stav projektu

Poslední kontrola: 2026-09-27.

Tento dokument rozlišuje implementovaný stav a plán.
Budoucí funkce nejsou automatickým zadáním k implementaci.

## Cíl
Školní a portfolio projekt přibližně na 90–100 hodin:
distribuovaný systém zpracování videa s centrálním webovým rozhraním.
Preferována je jednoduchost a postupný vývoj.

## Aktuální architektonická rozhodnutí
- Backend: Python, FastAPI, SQLAlchemy, Alembic a PostgreSQL.
- Frontend: React a Vite; Tailwind případně později.
- Backend, frontend a PostgreSQL mají používat Docker při vývoji
  i následně na VPS. Nginx se plánuje později.
- EDGE má běžet nativně, s vlastními Python závislostmi a virtualenv.
- Cílový edge systém je Linux / Debian / Raspberry Pi OS;
  automatické spouštění přes systemd přijde později.
- Docker není primární runtime pro EDGE. Případné Docker testování EDGE
  vyžaduje výslovné zadání.
- Důvodem nativního běhu je přímý přístup ke kamerám, síti,
  NetworkManageru, monitorování zařízení a systémovým operacím.
- Lokální edge úložiště bude pravděpodobně SQLite.
- Přesná databázová schémata, model rozpoznávání a synchronizační
  protokol zatím nejsou uzavřené.

## Implementováno
### Backend
- Existuje základní aplikace backend/app/main.py.
- Endpoint GET / vrací úvodní zprávu.
- Endpoint GET /health vrací {"status": "ok"}.
- Swagger /docs podle předchozího ověření uživatele funguje.
- requirements.txt obsahuje FastAPI a související backend závislosti.
- Databázové připojení, modely, migrace a autentizace nejsou implementované.

### Frontend
- Existuje React/Vite projekt s package-lock.json.
- UI je zatím výchozí demo, nikoli projektový dashboard.
- Vite má vývojovou proxy /api na backend; prefix /api se odstraní.
- Docker konfigurace zapíná polling pro sledování změn souborů.

### EDGE
- Existují složky cameras, config, demo, output, storage, tests a vision.
- Existuje requirements.txt a lokální virtuální prostředí.
- Neexistuje spustitelná vision aplikace.
- requirements.txt obsahuje OpenCV, ale ne DeepFace ani TensorFlow.
- Funkční instalace DeepFace ani rozpoznávání nebyly potvrzené.
- Dříve se objevil problém s dlouhou Windows cestou pod OneDrive;
  přesun na kratší cestu je možnost, nikoli dokončená změna.

## Aktuální Docker konfigurace
- Existují compose.yaml a Dockerfile/.dockerignore pro backend a frontend.
- Běžný Compose start spouští backend a frontend.
- Backend: port localhost:8000, reload, připojený backend/app a healthcheck.
- Frontend: port localhost:5173, Vite dev server a připojené zdrojové soubory.
- PostgreSQL v Compose zatím není.
- Docker podpora EDGE byla na výslovné zadání odstraněna: Dockerfile,
  .dockerignore, služba v Compose i deklarace jejího volume.
- README popisuje nativní Python prostředí EDGE na Windows a Linuxu.
- Současná konfigurace je vývojová, nikoli produkční.

## Dosavadní ověření
- Syntaxe compose.yaml byla ověřena YAML parserem.
- Lint frontendu prošel.
- Docker při přípravě nebyl dostupný v terminálu.
- Docker build, Compose validace a běh kontejnerů nebyly ověřené.
- Dostupnost a kompatibilita připnutých Python balíčků pro Linux
  nebyly ověřené.
- Git je inicializovaný; při kontrole před prvním commitem index neobsahoval soubory.
- Kořenový .gitignore pokrývá virtualenv, Python a frontend cache/build výstupy,
  tajemství, lokální databáze, logy a EDGE média včetně velkých přípon.
- Datové složky edge/recordings, targets, demo, output a storage ignorují obsah
  s výjimkou .gitkeep. Také skripty v edge/demo jsou nyní ignorované dle zadání.
- Výjimka pro .env.example zůstává pro šablony bez skutečných tajemství.
- Sdílená .vscode konfigurace se v kořenovém .gitignore plošně neignoruje;
  při kontrole nebyla nalezena. Existující frontend/.gitignore zůstal zachovaný.

## Nejbližší funkční milník
Malé nativní EDGE demo:
- vstupní historické video a volitelný referenční snímek,
- detekce a tracking,
- výběr přibližně 2–5 kvalitních vzorků na osobu,
- embeddingy a přiřazení nebo vytvoření anonymního profilu,
- reprezentativní snímky a JSON s časovými offsety,
- případné upozornění na shodu s referencí.

Jde o plán; implementovat až na konkrétní zadání.

## Pozdější rozsah
- Centrální osoby, vzorky, návštěvy, cíle a upozornění.
- Registrace edge zařízení, heartbeat, kamery a fronta povolených příkazů.
- Lokální matching, offline fronta a inkrementální synchronizace.
- Globálně jedinečné identity a případná centrální kontrola nových osob.
- Živé USB/RTSP vstupy a úsporný webový náhled.
- LAN a hotspot režim; ruční RTSP konfigurace je pro MVP přijatelná.
- CAMERA_STOP pro MVP zastavuje čtení streamu, nevypíná fyzickou kameru.
- Historický skutečný čas lze určit jen při známém začátku záznamu.
- Volitelně statistiky společného výskytu bez odvozování vztahů.
