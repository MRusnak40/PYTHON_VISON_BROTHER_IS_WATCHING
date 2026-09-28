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
