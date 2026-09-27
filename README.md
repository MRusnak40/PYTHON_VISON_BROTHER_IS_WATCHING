# Python Vision Detector

Samostatné aplikace `frontend`, `backend` a `edge`. Docker Compose je zde
připravený pro **lokální vývoj**, včetně automatického načítání změn kódu.

## Předpoklady

Na Windows nainstaluj a spusť [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
s WSL 2 a Linux kontejnery. Ověř `docker version` a `docker compose version`.
Lokální Python virtualenv ani Node.js nejsou pro běh v Dockeru potřeba.

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

Edge zatím nemá spustitelnou vision aplikaci. Má vlastní Dockerfile a volitelnou
službu v profilu `edge`, takže se při běžném `up` nesestavuje ani nespouští.
Interaktivní Python nebo shell spustíš takto:

```powershell
docker compose run --build --rm edge
docker compose run --build --rm edge sh
```

Až vznikne například `edge/demo/main.py`, spustíš ho:

```powershell
docker compose run --build --rm edge python demo/main.py
```

Celá složka `edge` je připojená do `/app`. Testovací video tedy může ležet
v `edge/recordings` a výsledky zapsané do `/app/output` zůstanou v `edge/output`
i po odstranění kontejneru. Tyto složky se neukládají do Gitu ani Docker image.
Volume `edge_models` je připravený pro případnou cache modelů DeepFace.

Současný `edge/requirements.txt` neobsahuje DeepFace ani TensorFlow.
Docker používá existující seznam závislostí; funkční rozpoznávání tváří tím
zatím není zajištěné. První sestavení zároveň ověří dostupnost a kompatibilitu
připnutých verzí pro Linux.

Tato konfigurace počítá s CPU a soubory videa. USB kamera, GPU a grafická okna
OpenCV vyžadují další nastavení zařízení/zobrazení. PostgreSQL zatím není
přidaný, protože backend dosud databázi nepoužívá.

## Ověření a omezení

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:5173/api/health
docker compose run --build --rm edge python -c "import cv2; print(cv2.__version__)"
```

Oba health požadavky mají vrátit `status: ok`. Pokud sestavení selže na
instalaci balíčku, zkontroluj konkrétní chybu a jeho připnutou verzi v příslušném
requirements souboru; současné verze nebyly při dockerizaci měněné.

Při přípravě této konfigurace nebyl Docker v prostředí dostupný, takže build
a běh kontejnerů zatím nebyly ověřené. Frontend běží přes vývojový Vite server
a backend přes reload režim; před veřejným nasazením bude potřeba produkční
konfigurace.

Použitá dokumentace: [Compose profily](https://docs.docker.com/compose/how-tos/profiles/)
a [Vite server, proxy a polling](https://vite.dev/config/server-options).
