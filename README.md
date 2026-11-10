# Python Vision Detector

Samostatné aplikace `frontend`, `backend` a `edge`. Docker Compose spouští
frontend a backend pro **lokální vývoj**, včetně automatického načítání změn
kódu. EDGE běží nativně ve vlastním Python prostředí.

Pro převzetí a pochopení kódu začni průvodcem [Jak funguje EDGE](docs/EDGE_CODE_GUIDE.md):
pořadí spuštění, tři souběžné smyčky, zpracování snímku a slovník proměnných.

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
OS, později se spouštěním přes systemd. Aplikace `edge/main.py` nyní zpracovává
živé RTSP a udržuje lokální profily; fyzická pipeline zatím nebyla ověřená.

### Spuštění živého zpracování ve Windows

Z kořene projektu jednorázově připrav konfiguraci:

```powershell
Set-Location C:\Users\matya\Desktop\PYTHON_VISION_DETECTOR
Copy-Item .\edge\config\.env.example .\edge\config\.env
notepad .\edge\config\.env
```

Kopírování vynech, pokud už `edge/config/.env` existuje. V něm vyplň
`CAMERA_RTSP_URL=rtsp://UZIVATEL:HESLO@IP_KAMERY:554/CESTA_STREAMU` skutečným
lokálním účtem kamery; cestu streamu převezmi z jejího nastavení nebo návodu.
Speciální znaky v uživateli/hesle URL zakóduj.
Proměnná prostředí má přednost před `.env`. Na topologii sítě nezáleží,
podstatná je dosažitelnost nakonfigurovaného endpointu. Soubor je ignorovaný Gitem.
Konfigurace celé EDGE aplikace je v `edge/config/`: `settings.py` obsahuje
nastavení zpracování a matchingu, `.env` místní přístupové údaje a `.env.example`
sdílenou šablonu bez hesel. `.env` se načítá nezávisle na pracovní složce.

```powershell
.\edge\.venv\Scripts\python.exe -X utf8 .\edge\main.py
```

Stejný vstup lze spustit pomocí `-m edge.main` nebo otevřením `edge/main.py`
a VS Code Run s vybraným `edge/.venv/Scripts/python.exe`. F5 / Ctrl+F5 používá
konfiguraci `EDGE: aplikace`, která také spouští přímo `edge/main.py`.
Další vývoj probíhá v aplikačních modulech; historická dema jsou archivovaná
v `TRASH/edge-cleanup-2026-11-10/edge/demo/`.
Zobrazí se náhled;
Q, Esc, zavření okna a Ctrl+C ukončí aplikaci. Čtení RTSP má timeout 10 s;
při odpojení aplikace oznámí chybu, uloží změněné časy a skončí.
Nové připojení vyžaduje znovu spustit příkaz.

### Připojení jiné RTSP kamery

Pro jinou značku nebo model změň pouze `CAMERA_RTSP_URL` v `edge/config/.env`
a znovu spusť aplikaci. Pokud máš stejnou proměnnou nastavenou v terminálu,
změň ji také tam, protože má přednost před `.env`.
Kamera musí poskytovat dosažitelný RTSP stream v kodeku podporovaném místním
OpenCV/FFmpeg a mít povolený přístup k videu. Shoda protokolu neznamená
ověřenou kompatibilitu všech modelů a kodeků.

Aplikace pouze přijímá obraz. Nastavení kamery, povolení streamu, polohu
a případný soukromý režim spravuj ručně v jejím vlastním rozhraní.
Při ukončení aplikace se stream odpojí; fyzická kamera se tím nevypíná.
Ovladač původní značky a jeho testy/demo jsou odpojené a uložené pro případné
vrácení v lokálním `TRASH/tapo-2026-11-10/README.md`, včetně původních verzí
upravených souborů. `TRASH/` je ignorovaný Gitem.

Náhled EDGE běží odděleně od inference; čtecí vlákno mezitím
uchovává jen poslední snímek. Výkon živého běhu není změřený.

### Živá identita, tracking a odezva

`main.py` čte RTSP a vykresluje nejnovější obraz. Jedno pracovní vlákno
v `vision/live.py` zpracovává snímky pomocí `VisionPipeline`. Má právě jedno
čekající místo: další příchozí snímek starý čekající přepíše. Kamera má také
jediný slot pro poslední načtený snímek. Nevzniká rostoucí fronta ani dohánění
historických snímků. Náhled se během embeddingu nemusí čekáním zastavit.
Při ukončení se dokončí případný právě běžící výpočet a teprve pak se
uloží poslední časy, aby do JSON nezapisovala dvě vlákna současně.

`vision/tracking.py` přiřazuje detekované obdélníky podle jejich překryvu (IoU).
Dočasný track má vlastní `track_id`; do JSON se neukládá. Neznámý track
sbírá kvalitní důkazy, teprve poté se naváže na trvalý `person_id`:

- Dvě jasné shody s týmž existujícím profilem vytvoří vazbu.
- Tři konzistentní použitelné embeddingy bez přijatelné shody mohou vytvořit
  jeden nový profil. Nekonzistentní důkazy nebo nejasná shoda zakládání odloží.
- Navázaný track už pro každý pohled neprohledává galerii a nemůže vytvořit
  jiný profil. Přímo aktualizuje svoji osobu. Před embeddingem dalšího vzorku
  se nejdřív zkontroluje kvalita a skutečná možnost přidání/náhrady.
- Při nejasném prostorovém překryvu se vazby raději zahodí. Po ztrátě
  detekce delší než 1,5 s track zanikne; při návratu se identita řeší znovu
  proti existujícím profilům. Krátká ztráta detekce vazbu zachová.

Jde o jednoduchý prostorový tracker, ne ověřené sledování při křížení lidí,
rychlém pohybu nebo úplném zakrytí tváře. Pokud někdo jiný obsadí stejnou
pozici mezi dvěma detekcemi, záměna je stále možná. Staré duplicitní profily
se automaticky neslučují; mohou způsobit stav `nejista shoda`.

Nastavení je soustředěné v `edge/config/settings.py`:

| Nastavení | Výchozí hodnota | Význam |
|---|---:|---|
| `process_interval` | 0,25 s | Pauza mezi dokončením detekce a dalším zpracováním |
| `recognition_interval` | 0,4 s | Nejmenší rozestup rozpoznávání neznámého tracku |
| `quality_interval` | 0,75 s | Hodnocení kandidáta u známého tracku |
| `detection_width` | 960 px | Největší šířka pro MTCNN, bez zvětšování malých vstupů |
| `sample_interval` | 2 s | Nejmenší rozestup zápisů fotek jednoho profilu |
| `identity_observations` / `match_observations` | 3 / 2 | Potvrzení nové / existující identity |
| `identity_quality` | 0,65 | Přísnější kvalita pro ustavení identity |
| `track_timeout` / `track_iou` / `track_margin` | 1,5 s / 0,20 / 0,10 | Ztráta detekce, překryv a nejasné přiřazení |
| `metrics_interval` | 5 s | Interval jednoduchého měření do terminálu |

Detekce používá zmenšený obraz. Souřadnice i landmarky se převedou zpět
a výřez, hodnocení jeho kvality i uložený JPEG používají původní rozlišení.
RTSP rozlišení ani kvalita kamery se nemění.

Terminál hlásí FPS oznámené kamerou, skutečnou četnost náhledu a zpracování,
počet embeddingů/matchingů za sekundu, průměrný čas embeddingu a detekce
a počet přeskočených čekajících snímků. Limit počtu snímků není slib FPS.
Čas embeddingu zahrnuje i tvorbu vybraných vzorků známých osob.

Kontrolované měření bez kamery 2026-10-19: u 100 zpracovaných syntetických
pozorování stejné nezměněné tváře původní cesta volala embedding/matching
100×/100×; nová 3×/4× (včetně kontroly galerie před založením), s jedním
profilem. Skutečný MTCNN po zahřátí na černém obrazu: průměr dvou detekcí
2560×1440 byl 730 ms, při šířce 960 px 127 ms. Jde o mikrotest bez lidí,
nikoli měření FPS, latence nebo přesnosti na živé kameře.

### Co se ukládá a co uvidíš

- Nový track po třech kvalitních konzistentních pozorováních bez shody:
  `Tn -> person-XXXX: created`, nový adresář
  a záznam v `edge/storage/profiles.json`. Existující ID/adresáře se nepřepisují;
  pokud už je `person-0001` rezervovaný adresář, první nové ID bude vyšší.
- Stejná osoba v navázaném tracku používá stejné ID i při změně úhlu. Aktualizuje
  `last_seen`; každý snímek se neukládá. Neviditelná/nekvalitní tvář nevytvoří profil.
- Chybějící pohled zleva, zepředu nebo zprava má přednost. Odlišný užitečný
  vzorek může přidat `sample_added`. Lepší kandidát může vyvolat
  `sample_replaced` i po zaplnění pěti míst. Zápisy vzorků dělí alespoň 2 s;
  pro zlepšení již obsazeného pohledu/doplňku je potřeba rozdíl skóre alespoň
  0,05. Nový chybějící pohled může nahradit doplněk i s nižším skóre,
  pokud prošel základní kvalitou. Podobné výřezy omezuje
  dHash, hrubý pohled určuje poloha nosu vůči očím, nejde o měřený úhel hlavy.
- Po návratu osoby i po restartu se embedding porovná s načtenými vzorky;
  dvě jasné shody vypíší `Tn -> person-XXXX: bound`. Menší cosine distance znamená větší
  podobnost, nikoli pravděpodobnost identity. Nejistá shoda mezi dvěma profily
  se přeskočí a v náhledu zobrazí `nejista shoda`.

Výchozí limit je 5 vzorků: jeden hlavní zleva (`left`), zepředu (`front`)
a zprava (`right`), nejvýše dva další vizuálně odlišné doplňky (`extra`).
V JSON má každý vzorek atribut `role`. Doplňky neobsadí místa rezervovaná
pro dosud nezachycené hlavní pohledy. Tři hlavní fotky stačí;
další dvě nejsou povinné. Chybějící pohled lze uložit až poté, co se osoba
příslušným směrem otočí a vznikne použitelný výřez. Fotky se negenerují ani
nezrcadlí. Levá/pravá označuje orientační směr tváře v obrazu podle landmarků,
nikoli anatomickou stranu s ověřeným úhlem. Úplný boční profil nemusí MTCNN rozpoznat.
Složka pak vypadá například takto (skutečné názvy mají celé náhodné UUID):

```text
edge/profiles/person-0002/
  face_left_a1b2...jpg
  face_front_c3d4...jpg
  face_right_e5f6...jpg
  face_front_1234...jpg   # volitelný doplněk
  face_left_5678...jpg    # volitelný doplněk
```

`representative_image` ukazuje na nejlepší z těchto souborů; další
`representative.jpg` se nekopíruje. Při úspěšné náhradě se slabší soubor odstraní.
JSON zachovává existující profily a obsahuje přibližně následující data
(embedding je zde pro přehlednost zkrácený, ve skutečnosti má 512 čísel):

```json
{
  "profiles": [
    {
      "person_id": "person-0002",
      "first_seen": "2026-10-19T18:00:00+00:00",
      "last_seen": "2026-10-19T18:00:10+00:00",
      "embedding_model": "Facenet512",
      "embedding_normalization": "base",
      "representative_image": "profiles/person-0002/face_front_a1b2.jpg",
      "face_samples": [
        {
          "path": "profiles/person-0002/face_front_a1b2.jpg",
          "role": "front",
          "captured_at": "2026-10-19T18:00:03+00:00",
          "quality": {
            "score": 0.91,
            "usable": true,
            "width": 180,
            "height": 200,
            "sharpness": 380.0,
            "confidence": 0.99,
            "view": "front",
            "fingerprint": "0123456789abcdef"
          },
          "embedding": [0.12, -0.03, 0.08]
        }
      ]
    }
  ]
}
```

Nový vzorek přidá položku; náhrada změní cestu, kvalitu a embedding příslušného
vzorku a případně reprezentativní obrázek. `first_seen` zůstává stejné,
`last_seen` se posouvá v UTC. Jde o čas pozorování, nikoli důkaz délky pobytu.
JSON se při změně vzorků zapisuje přes dočasný soubor a atomickou náhradu;
samotné časy se ukládají po 5 s a při řádném ukončení. Při pádu procesu
může zůstat nereferencovaný JPEG, ale starý vzorek se nemaže před uložením JSON.
Spouštěj jen jednu instanci nad stejným úložištěm.

Prázdný/chybějící JSON a chybějící datové složky jsou podporované. Neplatný
JSON nebo jiný model zastaví start bez přepsání souboru. Chybějící JPEG
vyvolá upozornění, embedding zůstává použitelný pro matching. Další vhodný
vzorek stejného pohledu může chybějící fotku obnovit i s nižším skóre;
reprezentativní obrázek se pak vybere z dostupných fotek.
Starším vzorkům bez `role` se role odvodí z uložené kvality;
samotné načtení žádné staré fotografie nemaže. Starší profil s pěti stejnými
pohledy postupně uvolní doplňková místa pro chybějící strany při jejich zachycení.
Biometrické snímky, celý adresář profilů i lokální JSON jsou ignorované Gitem.

Konstanty v `edge/config/settings.py` řídí intervaly, výběr vzorků a matching. Cosine práh 0,30
odpovídá výchozí hodnotě instalovaného DeepFace pro Facenet512. Kvalita
v `vision/quality.py` hodnotí velikost, ostrost, jas a detekční skóre.
Prahy ani hrubé rozlišení pohledů zatím nejsou kalibrované na této kameře;
chybná shoda i vytvoření duplicitní identity po ztrátě tracku jsou možné.
`VisionPipeline` přijímá snímek a časy a nezná přenosový protokol ani značku kamery. USB/MP4 adaptéry
nebyly v tomto úkolu přidané. Souběžná práce se stejným JSON více procesy
zůstává nepodporovaná.

### Ověření EDGE

Testy byly při úklidu 2026-11-10 přesunuté do
`TRASH/edge-cleanup-2026-11-10/edge/tests/`. Před přesunem prošlo všech 51 testů.
Návod k jejich obnovení je v `TRASH/edge-cleanup-2026-11-10/README.md`.
Kontrola syntaxe aktivního kódu:

```powershell
.\edge\.venv\Scripts\python.exe -X utf8 -m compileall -q edge/main.py edge/cameras edge/config edge/vision
```

Po obnovení testů do původní složky:

```powershell
.\edge\.venv\Scripts\python.exe -X utf8 -m unittest discover -s edge/tests -v
```

Po odpojení ovladače značky 2026-11-10 prošlo 51 automatických testů
se syntetickými daty: kvalita, matching,
restart, hlavní pohledy a dva doplňky, starší profily, omezení/náhrada vzorků,
konfigurace v `config/.env`, chyby persistence a simulovaný RTSP/runtime,
pořadí spuštění a úklid při chybách či Ctrl+C,
uložení metadat NumPy detektoru do JSON a bezpečná diagnostika chyb,
navázání tracku, změny úhlů, návrat, nekonzistentní důkazy, omezení výpočtů,
nejasné překryvy, nejnovější čekající snímek, původní rozlišení uložené fotky
a import obou vstupů aplikace bez otevření kamery. Samostatné kontroly ověřují
také interval pracovního vlákna a možnost obsloužit náhled/Q během blokující inference.
Prošly i skutečné importy, načtení MTCNN/Facenet512, detekce na prázdném
snímku a výpočet embeddingu syntetického výřezu. Živý stream s osobami,
přesnost rozpoznávání, zobrazené snímky a výkon tohoto nového běhu nebyly fyzicky
ověřené. Dřívější chyba zápisu NumPy metadat byla reprodukovaná a opravená bez kamery.

Výpisy oneDNN a upozornění na budoucí změny DeepFace/TensorFlow samy běh
neukončují. Při neočekávané chybě aplikace nyní vypíše například
`EDGE chyba pri matchingu a ukladani profilu: TypeError (vision/profiles.py:...).`
Text výjimky se nevypisuje, protože může obsahovat přístupové údaje.

### Ruční kontrola živé identity

Spusť `edge/main.py` výše uvedeným příkazem. Poznamenej si výchozí počet
profilů v JSON; existující data nemaž. Sleduj `Tn person-XXXX` v náhledu
a události `created`, `bound`, `sample_added`, `sample_replaced` v terminálu.

1. **A — změny úhlu:** oprávněný účastník zůstává v záběru. Podrž postupně
   čelní pohled, mírně vlevo, mírně vpravo a znovu čelně přibližně po 4–5 s.
   Po potvrzení identity očekávej stejné `Tn` a stejné `person-XXXX`, nejvýše
   jeden nový profil a postupné doplňování/zlepšení 3–5 fotek.
2. **B — návrat:** odejdi ze záběru alespoň na 3 s a vrať se nejprve čelně.
   Očekávej nový track, chvíli čekání a následné `bound` ke stávajícímu profilu,
   pokud vznikne jasná shoda. Nový profil nesmí vzniknout z jediného snímku.
3. **C — jiná osoba:** po odchodu první osoby vstoupí druhý oprávněný účastník.
   Po třech konzistentních důkazech bez přijatelné shody očekávej další profil.
   Při nejasné shodě má aplikace počkat místo okamžitého založení.

Sleduj i metriky; pro skutečné posouzení zpoždění porovnej pohyb ruky před
kamerou s náhledem na PC. Prahy, intervaly a zachycení bočních pohledů vyžadují
fyzickou kalibraci. Překřížení lidí a detekční výpadky testuj zvlášť.

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

Aktuální aplikace ukládá lokální stav do `edge/storage` a fotografie do
`edge/profiles`. Jejich obsah je ignorovaný Gitem s výjimkou `.gitkeep`.
Prázdná nepoužívaná složka `edge/output` byla přesunutá do archivu v `TRASH`.
Složky `edge/recordings` a `edge/targets` nyní aplikace nepoužívá.

`edge/requirements.txt` obsahuje DeepFace, TensorFlow, tf-keras a RetinaFace.
Na Windows s Pythonem 3.12 prošly importy a jednoduchý výpočet TensorFlow.
Model Facenet512 se načetl z existující cache `edge/.venv/.deepface/weights`
a inference na syntetickém výřezu prošla. Rozpoznávání skutečných osob
a kompatibilita na cílovém Linux zařízení zatím nejsou ověřené.
`DEEPFACE_HOME` se při startu aplikace nastaví na aktuální virtualenv,
pokud již není nastavený v prostředí. Na novém zařízení může první načtení
modelu vyžadovat stažení vah z internetu.

DeepFace může při výpisu zpráv v českém terminálu CP1250 selhat na
`UnicodeEncodeError`. Použij UTF-8 pro konkrétní spuštění:

```powershell
.\edge\.venv\Scripts\python.exe -X utf8 -c "from deepface import DeepFace; print('DeepFace OK')"
```

Stejný přepínač `-X utf8` dej před cestu ke svému Python skriptu.
Alternativně nastav `$env:PYTHONUTF8 = "1"` v daném terminálu před spuštěním.
Starší RTSP náhled je archivovaný v
`TRASH/edge-cleanup-2026-11-10/edge/demo/demo_v000/visionDemo_V000.py.disabled`;
aktuální profile pipeline spouštěj přes `edge/main.py`.

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
