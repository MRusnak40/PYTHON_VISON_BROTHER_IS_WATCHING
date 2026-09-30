# Stav projektu

Poslední aktualizace architektonického kontextu: 2026-09-28.
Implementační stav vychází z dosavadních kontrol; aktualizace roadmapy
neznamená nové ověření běhu aplikací.

Tento dokument rozlišuje implementovaný stav a plán.
Budoucí funkce nejsou automatickým zadáním k implementaci.

## Cíl
Školní a portfolio projekt přibližně na 90–100 hodin:
distribuovaný systém zpracování videa s centrálním webovým rozhraním.
Preferována je jednoduchost a postupný vývoj.
Jeden centrální backend a web sdružují více nezávislých EDGE zařízení,
z nichž každé může obsluhovat více kamer. Pokročilá analytika nesmí
zdržovat dokončení fungujícího jádra v dostupném časovém rozpočtu.

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
- EDGE zajišťuje vstupy, detekci, tracking, výběr vzorků, embeddingy,
  lokální matching, cache, neodeslané události a stav zařízení/kamer.
- Backend sjednocuje globální profily a pozorování, spravuje konfiguraci,
  cíle a příkazy a později počítá analytiku napříč kamerami a zařízeními.
- Cíle se spravují centrálně a synchronizují na příslušná EDGE zařízení;
  jejich běžné porovnávání probíhá lokálně.
- Kamera je samostatný koncept s vlastní identitou, přiřazeným EDGE,
  typem a zdrojem. Wi-Fi a Ethernet RTSP sdílejí vision implementaci.
- Název kamery a označení lokace mají být editovatelné z webu.
  Pro začátek postačí lokace jako atribut kamery, bez samostatné tabulky Location.
- Budoucí pozorování mohou obsahovat person_id, camera_id, edge_id,
  seen_from/seen_to, reprezentativní vzorek a metadata rozpoznání.
  Jde o koncept, nikoli schválené databázové schéma či požadavek rozšířit payload.

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
- requirements.txt obsahuje OpenCV, DeepFace 0.0.101, TensorFlow 2.21.0,
  tf-keras 2.21.0 a retina-face 0.0.18.
- Projekt je přesunutý do `C:\Users\matya\Desktop\PYTHON_VISION_DETECTOR`.
  Aktivační skripty, konfigurace a konzolové spouštěče obou virtualenv byly
  obnovené pro novou cestu. Neúplná instalace TensorFlow byla doplněná.
- Import DeepFace, OpenCV, TensorFlow a tf-keras prošel s `-X utf8`.
  Jednoduchý výpočet TensorFlow prošel; skutečné rozpoznávání a modelové
  váhy zatím nejsou ověřené. Demo visionDemo_V000.py je stále prázdné.
- DeepFace při výpisu Unicode zprávy do CP1250 selhával; README popisuje
  spuštění s UTF-8 bez změny globálního nastavení Windows.

## Aktuální Docker konfigurace
- Backend a frontend mají každý vlastní compose.yaml, Dockerfile a .dockerignore.
- Kořenový Compose byl nahrazen dvěma nezávislými projekty vision-backend
  a vision-frontend. Každý se spouští přes `docker compose up` ve své složce.
- Frontend při lokálním vývoji na Docker Desktop předává API požadavky přes
  host.docker.internal:8000 na publikovaný port backendu. Pro VPS bude síť
  nastavena zvlášť. UI lze spustit samostatně, API vyžaduje běžící backend.
- Backend: port localhost:8000, reload, připojený backend/app a healthcheck.
- Frontend: port localhost:5173, Vite dev server a připojené zdrojové soubory.
- PostgreSQL v Compose zatím není.
- Docker podpora EDGE byla na výslovné zadání odstraněna: Dockerfile,
  .dockerignore, služba v Compose i deklarace jejího volume.
- README popisuje nativní Python prostředí EDGE na Windows a Linuxu.
- Současná konfigurace je vývojová, nikoli produkční.

## Dosavadní ověření
- Po restartu byl skutečně ověřen Docker Engine 29.8.1 (Linux/amd64).
  Oba projekty úspěšně prošly `docker compose up --build -d --wait`.
  Backend `/health` vrátil status ok, frontend `/` HTTP 200 a frontendová
  proxy `/api/health` status ok. Opraven problém s HTTPS certifikáty při
  stahování závislostí: Dockerfile podporují volitelný build secret local_ca.
  Místní ignorované compose.override.yaml předávají veřejné kořenové
  certifikáty Windows z .docker/local-ca.pem; HTTPS ověřování zůstalo zapnuté.
  Certifikáty jsou připojené jen při instalaci pip/npm, nekopírují se do image.
  Po testu oba `docker compose down` odstranily kontejnery a sítě.
  Docker Desktop byl ukončený, jeho procesy nebyly nalezené a služba
  com.docker.service byla Stopped. Neběžela žádná WSL distribuce ani
  posluchač na portech 8000/5173. Image a build cache zůstaly na disku.
  Starší záznamy níže popisují průběh instalace a již vyřešené blokace.
- Docker runtime: Docker Desktop se úspěšně nainstaloval, Docker CLI je
  verze 29.8.1. Obě konfigurace prošly skutečným `docker compose config --quiet`.
  Engine zatím vracel HTTP 500; build ani kontejnery se nespustily.
  WSL 2.7.13 bylo následně úspěšně doinstalované jako správce.
  Virtual Machine Platform byla povolená přes DISM s výsledkem 3010
  (úspěch, nutný restart Windows). VirtualizationFirmwareEnabled=True.
  Po restartu je nutné spustit Docker Desktop, ověřit engine a dokončit
  `docker compose up --build -d` v backend/ a frontend/, včetně HTTP testů.
  Restart počítače nebyl automaticky provedený. Starší kontroly níže
  zachycují stav před instalací Dockeru a WSL.
- Kontrola Docker souborů 2026-09-30: Dockerfile, .dockerignore, Compose,
  build kontexty, COPY zdroje a bind-mount cesty byly staticky zkontrolované;
  nebyla nalezena chyba vyžadující změnu konfigurace. Node 22 splňuje
  deklarované požadavky Vite a pluginu React; npm lock neobsahuje file odkazy.
  Pip dry-run s Linux manylinux x86-64 / CPython 3.12 wheel tagy úspěšně
  vyřešil všechny připnuté backendové závislosti. Nejde o běh na Linuxu
  ani o Docker build; platformní podmínky se při této kontrole mohou lišit.
  Docker CLI není na PATH, Docker Desktop není v kontrolovaných běžných
  instalačních umístěních a WSL hlásí, že není nainstalovaný.
  `docker compose config`, build ani běh kontejnerů proto nebylo možné ověřit.
- Rozšířená kontrola přesunu 2026-09-30 odhalila ještě starou cestu ve dvou
  `pip3.12.exe`; oba spouštěče byly obnovené a jejich běh ověřený.
  Aktivace EDGE i backendu v PowerShellu vybírá správný Python a příkazy.
  V kontrolovaných souborech projektu a závislostí (s výjimkou Git internals,
  Python bytecode, médií a velkých binárních souborů) nebyly nalezené další
  odkazy na původní umístění. V projektu nejsou symlinky ani junctions.
  Git fsck nehlásí poškození; hlásí pouze nenavázané tree objekty.
  `npm ls --depth=0` prošlo. Lokální frontend a jeho proxy `/api/health`
  byly ověřené přes HTTP se spuštěným backendem; testovací procesy ukončené.
  YAML Compose a existence lokálních build/bind-mount cest byly ověřené.
  Projekt nemá `.vscode` ani `.idea`; výběr interpreteru uložený mimo projekt
  v IDE a již otevřené uživatelské terminály nebyly ověřené.
  Bez kopie před přesunem nelze porovnat úplnost ignorovaných dat a médií.
- Po přesunu a opravě 2026-09-30 prošel `pip check` pro EDGE i backend,
  importy DeepFace / OpenCV / TensorFlow / tf-keras a součet tensoru.
  Frontend prošel `npm run lint` a `npm run build`.
  Spouštěče pip.exe obou prostředí a backendový uvicorn.exe prošly kontrolou
  verze. Backend byl dočasně spuštěný na localhostu: HTTP `/`, `/health`,
  `/docs` a `/openapi.json` prošly; testovací server byl ukončený.
  Docker není dostupný v terminálu; kontejnery nebyly spuštěné.
  Níže uvedená první kontrola zachycuje stav před opravou.
- Dne 2026-09-30 prošel v `edge/.venv` import OpenCV (5.0.0) a `pip check`.
  Úspěch `pip check` nepotvrzuje úplnost TensorFlow: pip jej neeviduje,
  přestože jeho neúplná složka existuje. DeepFace není dostupný ani pro import.
  Windows mají `LongPathsEnabled=0`; souvislost s dřívějším selháním instalace
  je možná, ale bez původního chybového výpisu nepotvrzená.
  Soubor `edge/demo/demo_v000/visionDemo_V000.py` je prázdný.
  Při této kontrole nebyly balíčky ani nastavení Windows měněné.
- Dne 2026-09-28 byly zkontrolovány lokální Python 3.12.3 virtualenv:
  backend má 27 balíčků dle requirements, EDGE 63; verze odpovídají příslušným
  requirements.txt, navíc je pouze pip. Obě prostředí prošla `pip check`.
- Import FastAPI v backendu a OpenCV v EDGE prošel. DeepFace a TensorFlow
  nejsou nainstalované; úplná vision funkčnost tím nebyla ověřena.
- Lokální prostředí jsou izolovaná (`include-system-site-packages = false`).
  Jejich prompt je `vision-backend` a `vision-edge`; cesty `.venv` zůstaly stejné.
  Aktivace v PowerShellu a výběr správného pip byly ověřeny.
- Syntaxe obou samostatných compose.yaml byla ověřena YAML parserem.
- Lint frontendu prošel.
- Docker při přípravě nebyl dostupný v terminálu.
- Při kontrole 2026-09-28 nebyl příkaz Docker dostupný ani Docker Desktop
  ve standardním umístění. Konfigurace pro samostatné spuštění frontendu
  již existuje; README popisuje `docker compose up` v jednotlivých složkách
  a vysvětlení image, kontejneru, připojených souborů, sítě a proměnných.
- Původně neověřený Docker build, Compose a běh kontejnerů byly následně
  ověřené; aktuální výsledky jsou na začátku této sekce.
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

## Priority a pozdější rozsah

### P0 — funkční jádro, postupně po nejbližším milníku
- MP4, USB a RTSP vstupy se společnou pipeline; detekce, tracking,
  výběr vzorků, embeddingy, rozpoznávání a anonymní profily.
- Centrální osoby, vzorky, návštěvy, cíle a upozornění.
- Backend s PostgreSQL, React dashboard a správa kamer a EDGE zařízení.
- Registrace edge zařízení, heartbeat, kamery a fronta povolených příkazů.
- Lokální matching, offline fronta a inkrementální synchronizace.
- Globálně jedinečné identity a případná centrální kontrola nových osob.
- Živé USB/RTSP vstupy a úsporný webový náhled.
- LAN a hotspot režim; ruční RTSP konfigurace je pro MVP přijatelná.
- CAMERA_STOP pro MVP zastavuje čtení streamu, nevypíná fyzickou kameru.
- Historický skutečný čas lze určit jen při známém začátku záznamu.

### Budoucí / volitelná analytika — dosud neimplementováno

P1 (až po funkčním jádru):
- Časové osy osob napříč kamerami a EDGE, první/poslední pozorování,
  počet návštěv, často pozorované lokace a součet pozorovaného času.
- Rozšířená metadata kamery a návrh lokace podle scény.
- Centrální analytika společných výskytů a globální síť všech profilů,
  nikoli pouze ruční porovnání jedné dvojice.

P2:
- Vizualizace grafu, historie vzhledu a oblečení, přibližná kalibrovaná výška
  a pokročilejší analytika napříč kamerami.

Experimenty pouze při výrazné časové rezervě:
- Odhad hmotnosti (nízká spolehlivost, bez důležité navazující logiky),
  klasifikace viditelného výrazu a pokročilá analýza vzhledu těla.

### Návrh lokace kamery podle scény
- U nové kamery nebo nepotvrzené lokace může EDGE vybrat několik stabilních
  snímků, pokud možno bez lidí. Budoucí externí vision API může navrhnout
  např. chodbu či kuchyňku; backend uloží návrh a uživatel jej potvrdí/přejmenuje.
- Koncept location_source rozlišuje ai_suggested a user_confirmed.
  Poskytovatel API ani konkrétní model nejsou vybrané.
- Nevolat API pro každou osobu ani při každém reconnectu. Události využívají
  existující metadata kamery. Případná detekce změny scény nebo ruční akce
  „kamera přesunuta“ je budoucí možnost s dosud neurčenou metodou.

### Globální síť společných výskytů
- Osoba je uzel; spojení vyjadřuje naměřený společný výskyt. Backend může
  počítat počty společných pozorování/návštěv, časové překryvy, různé dny,
  kamery a lokace, první/poslední společný výskyt, aktuálnost, průměrnou délku
  překryvu a četnost relativně k individuálním návštěvám.
- Association/Co-occurrence Score má mít zdokumentovanou formuli; zatím není
  navržená. Hodnota 84/100 není 84% pravděpodobnost, že se lidé znají.
- Výsledky neprokazují přátelství, rodinný, partnerský, pracovní ani kriminální
  vztah. Délka pozorování neprokazuje pobyt mimo záběr ani přesnou trasu.

### Vzorky, vzhled a podmínky měření
- Preferovat přibližně 2–5 užitečných vzorků obličeje při průchodu,
  případně vybrané snímky těla; neuchovávat každý snímek ani neomezenou historii.
- Oblečení je proměnlivé metadata události, filtr či pomůcka krátkodobého
  trackingu. Vzhled těla může podpořit re-identifikaci, nikoli automaticky
  přebít spolehlivou identitu obličeje.
- Výška vyžaduje kalibraci scény/kamery a referenční geometrii;
  samotná výška postavy v pixelech nestačí. Hmotnost z RGB není přesné měření.
- Klasifikace viditelného výrazu (např. úsměv) není psychologické posouzení
  ani určení emocí, nebezpečnosti, lhaní, úmyslu či duševní poruchy.
- Očekávaná vzdálenost osob od kamery je přibližně 3–4 metry.
  Kvalitu je nutné ověřit na skutečné kameře, objektivu, rozlišení,
  umístění, osvětlení a úhlech; žádná přesnost zatím není změřená.

Konkrétní tabulky, endpointy, AI integrace a analytické algoritmy vzniknou
teprve na explicitní zadání. Pro každou funkci nejdřív zkontrolovat existující
kód a tento dokument, vysvětlit minimální změnu a nepřidávat nesouvisející funkce.
