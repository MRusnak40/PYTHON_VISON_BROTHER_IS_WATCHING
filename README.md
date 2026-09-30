# Python Vision Detector

Samostatné aplikace `frontend`, `backend` a `edge`. Docker Compose spouští
frontend a backend pro **lokální vývoj**, včetně automatického načítání změn
kódu. EDGE běží nativně ve vlastním Python prostředí.

## Předpoklady

Na Windows nainstaluj a spusť [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
s WSL 2 a Linux kontejnery. Ověř `docker version` a `docker compose version`.
Pro frontend a backend v Dockeru nepotřebuješ lokální Python virtualenv ani
Node.js. EDGE potřebuje lokální Python a vlastní virtuální prostředí.

## Samostatné spuštění frontendu a backendu

Každá aplikace má vlastní `Dockerfile`, `.dockerignore` a `compose.yaml`.
Kořenový Compose se nepoužívá. Docker Desktop musí běžet s Linux kontejnery.

Frontend spusť z kořene projektu v jednom terminálu:

```powershell
cd frontend
docker compose up
```

Otevři http://localhost:5173. Backend spusť z kořene v druhém terminálu:

```powershell
cd backend
docker compose up
```

Backend: http://localhost:8000, Swagger: http://localhost:8000/docs.
Při prvním spuštění se chybějící image sestaví automaticky; je potřeba internet.
Ctrl+C zastaví příslušnou aplikaci. Pro běh na pozadí použij `docker compose up -d`.
V odpovídající složce můžeš použít `docker compose logs -f`, `docker compose stop`
a `docker compose down`. Zastavení jedné aplikace nezastaví druhou.
Po změně závislostí použij v její složce `docker compose up --build`.

### Místní certifikáty při sestavení

Na tomto Windows počítači build původně selhal na ověření HTTPS certifikátu
při stahování z PyPI. Lokální `backend/compose.override.yaml` a
`frontend/compose.override.yaml` předávají `.docker/local-ca.pem` jako build
secret `local_ca`. PEM obsahuje veřejné důvěryhodné kořenové certifikáty
exportované z Windows; tyto tři místní soubory jsou ignorované Gitem.
Dockerfile používá certifikáty jen při instalaci balíčků přes `PIP_CERT`
a `NODE_EXTRA_CA_CERTS`; ověřování HTTPS zůstává zapnuté. Secret se neukládá
do výsledného image. Bez secretu se použije běžná důvěra základního image.

Příkaz `docker compose up --build` spuštěný ve složce backend nebo frontend
načte místní override automaticky. Při použití explicitního `-f compose.yaml`
přidej také `-f compose.override.yaml`, pokud chceš tuto místní konfiguraci.
Na jiném počítači export místních certifikátů přebírat nemusíš; záleží na síti.

Po práci spusť `docker compose down` v obou složkách a ukonči Docker Desktop
přes nabídku Quit nebo `docker desktop stop`. Image zůstanou uložené na disku,
ale nejsou to běžící procesy. `docker compose up` bez `-d` běží v popředí;
Ctrl+C zastaví kontejnery, Docker Desktop se tím sám nevypne.

### Co jednotlivé soubory dělají

`Dockerfile` sestavuje image, tedy prostředí s runtime, závislostmi a aplikací.
Kontejner je jeho spuštěná instance. Frontend používá Node.js a Vite, backend
Python a Uvicorn. `.dockerignore` vynechává z podkladů pro sestavení lokální
závislosti, cache a `.env` soubory. Lokální npm ani Python nejsou pro tyto
kontejnery potřeba.

Každý `compose.yaml` spravuje jednu službu jako samostatný projekt:
`vision-frontend` nebo `vision-backend`. Porty 5173 a 8000 jsou dostupné pouze
přes localhost. `volumes` připojují zdrojové soubory z počítače do kontejneru
(bind mounts); změny kódu se načítají automaticky. Závislosti jsou uvnitř image.
`VITE_USE_POLLING` a `WATCHFILES_FORCE_POLLING` zapínají sledování změn souborů
v prostředí Windows. Backend má navíc kontrolu dostupnosti `/health`.

### Komunikace aplikací při vývoji

Projekty mají samostatné Docker sítě. Frontend na Docker Desktop používá
`API_PROXY_TARGET=http://host.docker.internal:8000`: přes hostitelský počítač
se připojuje na publikovaný port backendu. Název `backend` mezi těmito
oddělenými sítěmi nefunguje. Toto propojení je určené pro lokální Docker Desktop;
pro VPS s nativním Linux Docker Engine bude potřeba samostatná síťová konfigurace.

Prohlížeč volá například `fetch('/api/health')` přes localhost:5173. Vite předá
požadavek backendu jako `/health`. UI může běžet samo, ale `/api` vyžaduje
spuštěný backend. Konfigurace sama do UI žádná API volání nepřidává.

## Edge

EDGE běží přímo na operačním systému kvůli přístupu ke kamerám, síťovým
adaptérům a systémovým službám. Cílový systém je Linux / Debian / Raspberry Pi
OS, později se spouštěním přes systemd. Zatím nemá spustitelnou vision aplikaci.

Pro vývoj ve Windows připravíš prostředí z kořene projektu takto
(pokud `edge/.venv` už existuje, první příkaz vynech):

```powershell
py -3.12 -m venv --prompt vision-edge edge/.venv
.\edge\.venv\Scripts\python.exe -m pip install -r edge/requirements.txt
```

Na Linuxu použij samostatné prostředí vytvořené na daném zařízení:

```bash
python3 -m venv --prompt vision-edge edge/.venv
edge/.venv/bin/python -m pip install -r edge/requirements.txt
```

Testovací videa patří do `edge/recordings`, reference do `edge/targets`,
výsledky do `edge/output` a lokální stav do `edge/storage`. Jejich obsah je
ignorovaný Gitem s výjimkou `.gitkeep`.

`edge/requirements.txt` obsahuje DeepFace, TensorFlow, tf-keras a RetinaFace.
Na Windows s Pythonem 3.12 prošly importy a jednoduchý výpočet TensorFlow.
Rozpoznávání na skutečných snímcích, váhy modelů a kompatibilita na cílovém
Linux zařízení zatím nejsou ověřené.

DeepFace může při výpisu zpráv v českém terminálu CP1250 selhat na
`UnicodeEncodeError`. Použij UTF-8 pro konkrétní spuštění:

```powershell
.\edge\.venv\Scripts\python.exe -X utf8 -c "from deepface import DeepFace; print('DeepFace OK')"
```

Stejný přepínač `-X utf8` dej před cestu ke svému Python skriptu.
Alternativně nastav `$env:PYTHONUTF8 = "1"` v daném terminálu před spuštěním.
Demo `edge/demo/demo_v000/visionDemo_V000.py` je zatím prázdné.

Po přesunu projektu je potřeba obnovit virtuální prostředí; jejich aktivace
nebo spouštěče mohou obsahovat původní absolutní cestu. V IDE znovu vyber
`edge/.venv/Scripts/python.exe` z aktuálního umístění projektu.

PostgreSQL zatím není v Compose přidaný, protože backend dosud databázi
nepoužívá.

## Rozlišení lokálních Python prostředí

Složky zůstávají `backend/.venv` a `edge/.venv`; po aktivaci se v terminálu
zobrazí `(vision-backend)` nebo `(vision-edge)`. Existující prostředí mají
nastavené tyto názvy v aktivační konfiguraci. Virtuální prostředí se necommitují.
Při novém vytvoření použij `--prompt vision-backend` nebo `--prompt vision-edge`.

Z kořene projektu v PowerShellu aktivuj požadované prostředí:

```powershell
.\backend\.venv\Scripts\Activate.ps1
# Před přepnutím ukonči předchozí prostředí:
deactivate
.\edge\.venv\Scripts\Activate.ps1
```

V již otevřeném terminálu prostředí deaktivuj a znovu aktivuj, aby se nový
název projevil. Interpreter ověříš příkazem `python -c "import sys; print(sys.executable)"`.
Pro instalaci používej `python -m pip`, nebo ještě jednoznačněji přímo cestu:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\edge\.venv\Scripts\python.exe -m pip install -r edge/requirements.txt
```

Tyto dva příkazy míří do správného prostředí bez ohledu na aktivaci terminálu.
Při spouštění přes IDE vyber odpovídající interpreter z příslušné `.venv`.

## Ověření a omezení

```powershell
docker compose -f backend/compose.yaml config --quiet
docker compose -f frontend/compose.yaml config --quiet
docker compose -f backend/compose.yaml up --build -d
docker compose -f frontend/compose.yaml up --build -d
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:5173/api/health
```

Oba health požadavky mají vrátit `status: ok`. Pokud sestavení selže na
instalaci balíčku, zkontroluj konkrétní chybu a jeho připnutou verzi v příslušném
requirements souboru; současné verze nebyly při dockerizaci měněné.

Build i spuštění obou kontejnerů byly ověřené na Docker Desktop s WSL 2,
včetně HTTP kontroly backendu, frontendu a proxy `/api/health`. Frontend běží přes vývojový Vite server
a backend přes reload režim; před veřejným nasazením bude potřeba produkční
konfigurace.

Použitá dokumentace: [Vite server, proxy a polling](https://vite.dev/config/server-options).
