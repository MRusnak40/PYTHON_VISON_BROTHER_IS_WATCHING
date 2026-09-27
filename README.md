# Python Vision Detector

Samostatné aplikace `frontend`, `backend` a `edge`. Docker Compose spouští
frontend a backend pro **lokální vývoj**, včetně automatického načítání změn
kódu. EDGE běží nativně ve vlastním Python prostředí.

## Předpoklady

Na Windows nainstaluj a spusť [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
s WSL 2 a Linux kontejnery. Ověř `docker version` a `docker compose version`.
Pro frontend a backend v Dockeru nepotřebuješ lokální Python virtualenv ani
Node.js. EDGE potřebuje lokální Python a vlastní virtuální prostředí.

## Frontend a backend

V kořenové složce projektu spusť:

```powershell
docker compose up --build -d
docker compose ps
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Kontrola backendu: http://localhost:8000/health

Změny v `backend/app` a `frontend/src` se načítají automaticky. Polling je
zapnutý kvůli sledování souborů upravených ve Windows. Balíčky se instalují
uvnitř Linux image; Windows `.venv` a `node_modules` se do image nekopírují.
Po změně závislostí znovu spusť `docker compose up --build -d`.

```powershell
docker compose logs -f
docker compose stop
docker compose up -d
docker compose down
```

Pouze backend lze spustit příkazem `docker compose up --build -d backend`.
Stejně lze samostatně spustit `frontend`.

Frontend může volat například `fetch('/api/health')`. Vite proxy předá
požadavek backendu jako `/health`, takže při lokálním vývoji není nutné
přidávat CORS. Ověření proxy: http://localhost:5173/api/health.
Adresa `backend:8000` funguje mezi kontejnery; prohlížeč používá `localhost`.
Konfigurace proxy sama do UI žádné volání API nepřidává.

## Edge

EDGE běží přímo na operačním systému kvůli přístupu ke kamerám, síťovým
adaptérům a systémovým službám. Cílový systém je Linux / Debian / Raspberry Pi
OS, později se spouštěním přes systemd. Zatím nemá spustitelnou vision aplikaci.

Pro vývoj ve Windows připravíš prostředí z kořene projektu takto
(pokud `edge/.venv` už existuje, první příkaz vynech):

```powershell
py -3.12 -m venv edge/.venv
.\edge\.venv\Scripts\python.exe -m pip install -r edge/requirements.txt
```

Na Linuxu použij samostatné prostředí vytvořené na daném zařízení:

```bash
python3 -m venv edge/.venv
edge/.venv/bin/python -m pip install -r edge/requirements.txt
```

Testovací videa patří do `edge/recordings`, reference do `edge/targets`,
výsledky do `edge/output` a lokální stav do `edge/storage`. Jejich obsah je
ignorovaný Gitem s výjimkou `.gitkeep`.

Současný `edge/requirements.txt` neobsahuje DeepFace ani TensorFlow.
Funkční rozpoznávání tváří ani kompatibilita všech připnutých závislostí
na cílovém zařízení zatím nejsou ověřené.

PostgreSQL zatím není v Compose přidaný, protože backend dosud databázi
nepoužívá.

## Ověření a omezení

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:5173/api/health
```

Oba health požadavky mají vrátit `status: ok`. Pokud sestavení selže na
instalaci balíčku, zkontroluj konkrétní chybu a jeho připnutou verzi v příslušném
requirements souboru; současné verze nebyly při dockerizaci měněné.

Při přípravě této konfigurace nebyl Docker v prostředí dostupný, takže build
a běh kontejnerů zatím nebyly ověřené. Frontend běží přes vývojový Vite server
a backend přes reload režim; před veřejným nasazením bude potřeba produkční
konfigurace.

Použitá dokumentace: [Vite server, proxy a polling](https://vite.dev/config/server-options).
