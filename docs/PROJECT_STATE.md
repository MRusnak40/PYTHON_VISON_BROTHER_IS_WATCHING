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
- Úklid adresáře 2026-11-10: do `TRASH/edge-cleanup-2026-11-10/edge/`
  byly přesunuté `tests/`, historické `demo/`, prázdné nepoužívané `output/`
  a `edge/TRASH/`. Po upřesnění zadání zůstává vše používané při spuštění
  `edge/main.py`, včetně cache: čtyři složky `__pycache__/` z kořene EDGE,
  cameras, config a vision byly obnovené na původní místa (9 souborů,
  obsah ověřený SHA-256). Testy ani historická dema se neobnovovaly.
  Archiv nyní obsahuje 14 původních souborů; všech 6 archivovaných Python zdrojů má
  příponu `.py.disabled`, aby se nespouštěly ani nesbíraly jako testy.
  `manifest.json` eviduje původní/cílové cesty, velikosti a SHA-256
  původního přesunu i seznam obnovených cache v sekci `Restoration`;
  README archivu popisuje obnovu. Celý kořenový `TRASH/` zůstává ignorovaný Gitem.
  Aktivní zdroje, requirements, konfigurace včetně místního `.env` a
  `storage/profiles.json` zůstaly obsahově beze změny (13 souborů ověřených hashem).
  `.venv/` včetně modelů a `profiles/` zůstávají pro běh a ukládání dat.
  Před přesunem prošlo 51 automatických testů. Po přesunu prošla kontrola
  syntaxe všech 9 aktivních modulů, obou variant importu bez otevření kamery,
  úplnosti archivu podle hashů a ignorování archivu i citlivých dat Gitem.
  Návody odkazují na archiv;
  starší záznamy níže popisují původní umístění. Kamera ani GUI se při úklidu
  nespouštěly; úklid nemění vision pipeline ani závislosti.
- Odpojení ovladače značky 2026-11-10: hlavní aplikace nyní používá pouze
  obecný RTSP zdroj. Importy ovládání, inicializace/úklid ovladače, příkazy
  soukromí a klávesové otáčení jsou z aplikačního kódu odstraněné.
  `Settings`, načítání konfigurace a `.env.example` už nemají přepínač
  ovladače ani parametry otáčení; `pytapo` je odstraněné z requirements.
  Místní `CAMERA_RTSP_URL` v `edge/config/.env` byla zachovaná bajt po bajtu;
  odstraněné bylo jen nastavení ovladače a související komentáře.
  Soubory `cameras/control.py`, `cameras/tapo.py`, `tests/test_privacy.py`
  a `demo/test_rtsp_camera.py` jsou přesunuté do `TRASH/tapo-2026-11-10/`.
  Archiv obsahuje i původní verze upravených souborů a návod k obnově.
  Python soubory archivu mají příponu `.py.disabled`, aby se nespouštěly
  ani nesbíraly jako testy. Celé `TRASH/` je ignorované Gitem.
  Obecné scénáře startu, chyb a úklidu zůstávají v `tests/test_application.py`;
  ostatní runtime testy jsou upravené pro samotné RTSP. Prošlo 51 testů
  i s výslovně zablokovaným importem původní knihovny ovladače.
  Syntaxe aktivních zdrojů a testů, kontrola chybějících odkazů na ovladač,
  úplnost archivu a vyloučení `TRASH/` i `.env` z Gitu byly ověřené.
  Pro jinou RTSP kameru stačí změnit URL a restartovat aplikaci, pokud je
  její stream dostupný a kodek podporovaný místním OpenCV/FFmpeg.
  Povolení streamu, soukromí a polohu kamery nyní spravuje uživatel ručně.
  USB/MP4 adaptéry se nepřidávaly; kompatibilita všech kamer není ověřená.
  Fyzická kamera, živé GUI a přesnost rozpoznávání při této změně nebyly ověřované.

#### Historie EDGE

Následující záznamy zachovávají dřívější stav a výsledky kontrol. Popisy
ovládání původní kamery níže již neodpovídají aktuálnímu aplikačnímu kódu.

- Zpřehlednění kódu 2026-11-10: `main.py` nyní obsahuje `EdgeApplication`.
  Veřejný vstup `main()` i přímé a balíčkové spuštění zůstávají zachované.
  Příprava modelů, připojení kamery, GUI smyčka, vykreslení, vstup a úklid
  mají samostatné metody. Při neočekávané chybě otevření RTSP se nově hlásí
  přímo fáze spojení místo předchozí fáze přípravy ovládání.
  V `VisionPipeline` je oddělené potvrzování existující/nové osoby a zlepšování
  známého profilu; `LiveWorker` odděluje čekání na vstup od výpočtů a metrik.
  Tracker má dílčí metody pro zánik, nejasnosti, přiřazování a chybějící detekce.
  Úložiště odděluje validaci profilu/vzorku, výběr doplňku, přípravu profilu
  a zápis JPEG/JSON; kvalita má samostatný odhad pohledu a dHash.
  `PipelineResult`, `WorkerSnapshot` a `MatchResult` pojmenovávají položky
  návratových hodnot při zachování původního rozbalování a indexování.
  V 11 aplikačních Python modulech jsou rozšířené české komentáře proměnných,
  vstupů/výstupů a viditelné oddíly; důležité smyčky jsou označené A–D.
  `docs/EDGE_CODE_GUIDE.md` popisuje přesné pořadí startu, tři aplikační vlákna,
  předávání snímků, rozhodování o identitě, ukládání, úklid a složitější proměnné.
  Bez nových závislostí a bez změn prahů, schématu JSON nebo historických dem.
  Ověření: 62 testů prošlo (původních 59 a 3 nové pro náhled a fázi chyby RTSP);
  existující test navíc ověřuje dokončení inference před závěrečným flush.
  Syntaxe aplikačních modulů a testů i kontrola whitespace prošly.
  Fyzická kamera, ovládání Tapo, skutečné GUI, přesnost rozpoznávání a živé FPS
  při této úpravě nebyly ověřované; aplikace nebyla připojena ke skutečné kameře.
- Změna živého lifecycle 2026-10-19: `vision/pipeline.py` nyní používá
  dočasný prostorový IoU tracker z `vision/tracking.py`. Neznámý track
  čeká na 2 jasné shody se stejným profilem nebo 3 kvalitní konzistentní
  embeddingy bez shody před založením. Naváže se `track_id → person_id`;
  další úhly stejného tracku aktualizují přímo tento profil bez hledání
  galerie a bez možnosti založit další osobu. Nekvalitní/nekonzistentní
  důkazy a nejasné shody založení odkládají. Práh cosine distance zůstává
  0,30; více vzorků každého profilu se dále účastní matchingu.
  Track zaniká po 1,5 s od první chybějící detekce; nejasný prostorový
  překryv ruší vazby. Tracker ID se nepersistuje. Stávající duplicity se
  automaticky neslučují. Křížení/zakrytí a záměna při obsazení stejného
  místa jinou osobou zůstávají omezením jednoduchého trackeru.
  Detekce má pauzu 0,25 s, embedding neznámého tracku nejméně 0,4 s,
  kvalita známého tracku 0,75 s; diskový rozestup fotek zůstává 2 s.
  Známý track tvoří embedding pouze po úspěšném předvýběru vzorku.
  MTCNN používá nejvýše šířku 960 px, ale výřezy a JPEG zůstávají z originálu.
  `vision/live.py` odděluje inference od GUI; má jen jeden přepisovaný
  čekající snímek, stejně jako RTSP čtečka. Žádná rostoucí fronta.
  Při ukončení se čeká na právě běžící výpočet před posledním zápisem JSON.
  Terminál měří hlášené FPS kamery, náhled/zpracování za sekundu, počet
  embeddingů a matchingů, časy výpočtů a přeskočené čekající snímky.
  `main.py` nyní používá obecné volitelné ovládání `cameras/control.py`;
  pytapo se načte pouze při výslovném `CAMERA_TAPO_PRIVACY=1`. Obecný výchozí
  stav i šablona mají 0, místní Tapo nastavení zůstalo 1. Adaptér zachovává
  soukromí a WASD, bez změn historického dema. Samotná pipeline přijímá
  libovolné BGR snímky a nezávisí na výrobci ani zdroji. USB/MP4 adaptéry
  se zatím nepřidávaly. Profily zůstávají omezené na hlavní 3 + nejvýše 2
  doplňkové vzorky. Při chybějících JPEG se zachovají použitelné embeddingy
  a identita; fotky se mohou obnovovat při dalším pozorování.
  Prošlo 59 testů, syntaxe, import bez pytapo a skutečný MTCNN/Facenet512
  s uložením syntetického výřezu do dočasného profilu. V kontrolovaném
  testu 100 nezměněných pozorování klesly embeddingy 100→3 a matchingy 100→4.
  MTCNN na černém obrazu (2 běhy po zahřátí): 2560×1440 průměr 730 ms,
  šířka 960 px 127 ms. Nejde o živé FPS ani přesnost. Nová pipeline,
  tracking napříč úhly a latence s fyzickou kamerou dosud NEOVĚŘENÉ.
- Diagnostika uživatelského běhu 2026-10-19: log potvrzuje načtení modelů,
  vypnutí soukromí, start hlavní smyčky a opětovné zapnutí soukromí po chybě.
  Původní obecná hláška neobsahovala skutečnou výjimku, takže samotný log
  neurčuje její přesné místo. Následně se bez kamery podařilo reprodukovat
  chybu prvního zápisu profilu: MTCNN vrací confidence jako NumPy float32/64,
  výpočet kvality jej propagoval do metadat a JSON selhal na TypeError
  (float32 nebo NumPy bool). `vision/quality.py` nyní převádí confidence na
  Python float před výpočtem; `vision/faces.py` převádí souřadnice na int.
  `main.py` při neočekávané chybě nově vypisuje fázi, typ výjimky a poslední
  aplikační soubor/řádek, bez textu výjimky nebo tajemství.
  Prošlo 40 automatických testů a syntaxe. Navíc prošel skutečný Facenet512
  embedding syntetického výřezu → JSON → opětovné načtení profilu s oběma
  typy confidence z formatteru instalovaného MTCNN (detekce byla simulovaná).
  Opravený běh na fyzické kameře zatím nebyl znovu ověřený.
- Doplnění 2026-10-19: `edge/main.py` nyní po načtení modelů automaticky
  vypne soukromí Tapo před RTSP a ověří `off`; při řádném ukončení, Ctrl+C
  nebo ošetřené chybě jej zapne a ověří `on`. Řídí to `cameras/tapo.py`
  přes stávající pytapo a účet z lokálního RTSP URL. Zapnutí soukromí má
  při úklidu přednost před uzavřením RTSP a zápisem posledních časů.
  Selhání autentizace neposílá příkazy; po zahájeném pokusu vypnout soukromí
  se obnovení zkusí i při následné chybě RTSP nebo nepotvrzeném vypnutí.
  Nepotvrzené zapnutí vypíše varování a vrátí chybový kód. Násilné ukončení
  procesu/výpadek napájení úklid neprovede. `CAMERA_TAPO_PRIVACY=1` v
  `config/.env` je výchozí nastavení, `0` ponechá pouze obecné RTSP.
  Prošlo 38 automatických testů, syntaxe a import pytapo/aplikace.
  Přepínání soukromí z tohoto nového main nebylo fyzicky ověřené.
- Upřesnění 2026-10-19: vstupem celé aplikace zůstává `edge/main.py`;
  VS Code F5 / Ctrl+F5 nyní používá `EDGE: aplikace` s tímto souborem.
  Další implementace patří do aplikačních modulů, `edge/demo/` slouží pouze
  jako historický pokus. Konfigurace včetně místního `.env` a sanitizované
  `.env.example` je sjednocená v `edge/config/`. Existující místní kamerové
  údaje byly zachované v ignorovaném `edge/config/.env`.
  Výběr nyní chrání tři hlavní pohledy `left`, `front`, `right` a dovoluje
  nejvýše dva odlišné doplňky. Vzorky mají v JSON atribut `role` a jméno
  souboru zahrnuje zachycený pohled. Tři hlavní fotky stačí; dva doplňky
  nejsou povinné a neblokují doplnění dosud chybějících stran.
  Chybějící pohled má přednost před doplňkem i s nižším skóre, pokud je
  použitelný. Zlepšování obsazeného pohledu nadále vyžaduje rozdíl ≥ 0,05.
  Starším vzorkům se role odvodí bez smazání při načtení. Složky nových osob
  dál vznikají automaticky při prvním uložení vzorku. Pohledy jsou pouze
  heuristika landmarků ve směru obrazu; chybějící strana se nevyrábí,
  úplný boční profil nemusí detektor zachytit. Fyzicky neověřeno.
  Prošlo 23 automatických kontrol včetně tří hlavních pohledů, rezervace
  míst, dvou doplňků, starších profilů a načítání konfigurace. Syntaxe prošla.
- Dne 2026-10-19 byla implementována skutečná aplikace `edge/main.py`:
  RTSP → MTCNN → hodnocení výřezu → Facenet512 → lokální matching → JSON/profily.
  Při kontrole byly připravené aplikační moduly a `storage/profiles.json`
  prázdné; existující video demo obsahovalo pouze MTCNN a ukládání výřezů,
  nikoli matching, tracking nebo kvalitu. Nové jádro navazuje na tento postup.
  `cameras/source.py` přebírá OpenCV/FFmpeg RTSP postup a timeouty z náhledu;
  jedno čtecí vlákno drží jen nejnovější snímek během výpočtu vision.
  Tapo/PTZ demo zůstalo beze změny. Aplikace neovládá pohyb kamery;
  automatické soukromí bylo následně doplněno, viz aktuální záznam výše.
  Konfigurace URL: proměnná `CAMERA_RTSP_URL` nebo ignorovaný `edge/config/.env`.
  JSON používá relativní cesty, UTC first_seen/last_seen, model a embeddingy
  jednotlivých vzorků. Chybějící/prázdný JSON znamená prázdné úložiště;
  neplatný JSON aplikaci zastaví bez přepsání dat. Existující adresáře ID
  jsou rezervované. Lokální store je určený pro jeden proces aplikace.
  Výběr uchovává nejvýše 5 vzorků; podobné výřezy omezuje dHash a orientační
  poloha nosu vůči očím. Další zápis vzorku nejdříve po 2 s, náhrada při
  zlepšení skóre alespoň o 0,05. Reprezentativní obrázek odkazuje na nejlepší
  uložený vzorek, nevzniká další kopie. Při jediném vhodném pohledu může zůstat
  jen 1 vzorek; minimum 2 se nevynucuje duplicitami. last_seen se průběžně
  ukládá nejvýše po 5 s a při řádném ukončení. Vzorky se ukládají okamžitě.
  Matching používá cosine distance ≤ 0,30 (výchozí práh instalovaného
  DeepFace pro Facenet512); při odstupu dvou nejlepších profilů < 0,05
  pozorování přeskočí. Tracking ani evidence návštěv zatím nevznikly.
  Prahy kvality/matchingu jsou heuristiky, přesnost ani výkon nejsou změřené;
  chybné sloučení i rozdělení identity zůstává možné. Odpojení streamu
  ukončí běh se srozumitelnou chybou; automatický reconnect není implementovaný.
  Ověřeno: syntaxe, importy, skutečné načtení MTCNN/Facenet512, prázdný snímek
  a 512prvkový embedding syntetického výřezu, 18 automatických kontrol
  kvality, persistence, náhrad, restartu, chyb zápisu a simulovaného runtime.
  Fyzická RTSP pipeline, náhled GUI a rozpoznávání skutečných osob při této
  implementaci NEBYLY ověřené. Bez nových závislostí. Návod a schéma v README.
- Dne 2026-10-19 bylo na žádost uživatele v existujícím lokálním
  `edge/demo/test_rtsp_camera.py` nahrazeno automatické otáčení při
  ukončení ručním ovládáním W/A/S/D během náhledu. W/S ovládá nahoru/dolů,
  A/D doleva/doprava po 10°; fungují i velká písmena. Aktivní musí být
  okno OpenCV. Pohybové požadavky mají minimální rozestup 0,3 s;
  chyba pohybu sama neukončí náhled. Zůstává vypnutí soukromí při startu
  a zapnutí s ověřením při Q, Esc, zavření okna nebo chybě.
  Prošly syntaxe, importy a 19 simulovaných kontrol hlavní smyčky
  (směry, omezení opakování, chyby, úklid a opakované běhy bez pohybu
  při ukončení). Fyzický pohyb a klávesnice ve skutečném okně nebyly
  při této úpravě ověřené. Bez nových závislostí a aplikačních souborů.
  Níže je zachovaná diagnostika před nahrazením automatického pohybu.
- Kontrola 2026-10-19 kvůli opakovanému otáčení v
  `edge/demo/test_rtsp_camera.py`: v EDGE prostředí prošly importy OpenCV
  a pytapo, připojení ovládání Tapo i načtení RTSP snímku 2560 × 1440.
  `getCruise()` vrátil stav `idle`; soukromý režim byl hlášený jako `on`.
  Kontrola neposílala pohybové příkazy ani neměnila soukromý režim.
  Skript při každém ukončení posílá `moveMotor(-180, 0)` a při spuštění
  nevrací směr zpět. Referenční integrace autora pytapo používá tuto
  metodu pro relativní posun; opakovaný pohyb doleva proto pravděpodobně
  dosáhne mechanického dorazu (výrobce pro C220 uvádí rozsah 340°).
  Dosažení dorazu nebylo fyzicky ověřené; opakované otáčení zůstává
  neopravené. Testovací skript ani závislosti se při kontrole neměnily.
- Dne 2026-10-14 byl na výslovnou žádost zjednodušen
  `edge/demo/test_rtsp_camera.py`: adresu uživatel zadává přímo do `RTSP_URL`
  nahoře v souboru. Proměnná prostředí ani `.env` se v tomto testu nečtou.
  Soubor s adresou a přihlašovacími údaji je lokální, ignorovaný Gitem
  a není sledovaný. Zachovaný náhled, Q, timeouty a úklid zdrojů.
  Syntaxe, importy a kontrola nevyplněné adresy prošly; simulované ukončení Q
  a chyby otevření, čtení i OpenCV ověřily úklid a nevypisování tajemství.
  Dne 2026-10-14 uživatel potvrdil funkční živý RTSP náhled z fyzické
  Tapo C220 připojené přes hotspot vývojového PC. Tím je uživatelem
  ověřená konektivita a příjem obrazu. Níže je historie původní verze testu.
- Dne 2026-10-13 vznikl samostatný test fáze 1
  `edge/demo/test_rtsp_camera.py`: ručně nastavené `CAMERA_RTSP_URL`
  pouze z prostředí, OpenCV/FFmpeg náhled, hlášené rozlišení/FPS,
  ukončení Q a uvolnění zdrojů při chybě či ukončení. Otevření i čtení
  mají timeout 10 s. Kód nenastavuje síťové adaptéry ani směrování.
  Závislosti se neměnily; složka demo zůstává ignorovaná Gitem.
  Prošla kontrola syntaxe/importů v `edge/.venv` (OpenCV 5.0.0, FFmpeg
  dostupný), skutečné spuštění větve bez URL a sedm simulovaných kontrol:
  selhání otevření/čtení, prázdný snímek, q/Q, chyba OpenCV a Ctrl+C.
  U simulací bylo ověřeno uvolnění zdrojů a nevypisování URL aplikací.
  Při přípravě nebylo v prostředí `CAMERA_RTSP_URL`, fyzické ověření
  tehdy čekalo na potvrzení uživatele (potvrzeno 2026-10-14 výše). Nejde o implementaci
  plné podpory kamer ani navazující vision pipeline.
- Dne 2026-10-13 byly na výslovnou žádost opravené překlepy v uživatelově
  `edge/demo/demo_v001/main.py`: převod BGR na RGB, název `face_folder`,
  volání `cv2.imwrite` a název `detected_faces`. Uvolnění videa je chráněné
  pro případ chyby před jeho otevřením. Skript má hledat obličeje přes MTCNN
  a skončit po uložení výřezů prvního snímku s detekcemi; nemá ještě výběr
  kvality, odhad natočení, identifikaci ani zápis profilů. Syntaxe ověřená;
  celý běh s detektorem a ukládáním nebyl při této opravě spuštěný.
- Opakovaná kontrola 2026-10-08: žádné chybějící balíčky, odlišné verze ani
  chybějící soubory proti `edge/requirements.txt` a instalačním RECORD.
  Zkontrolováno 21 922 hashů; odlišnosti se týkají konzolových spouštěčů
  a sdílených doprovodných README/requirements/package_info, ne vlastních
  souborů knihoven. ZIP integrita a interpreterové cesty spouštěčů prošly.
  `pip check`, importy OpenCV, NumPy, TensorFlow, tf-keras, h5py, DeepFace,
  RetinaFace, MTCNN a dotenv i výpočet TensorFlow prošly; bez reinstalace.
  Váhy Facenet512 se nyní úspěšně stáhly přes PowerShell s ověřováním HTTPS
  do `edge/.venv/.deepface/weights/facenet512_weights.h5` (94 955 648 bajtů).
  Prošlo otevření HDF5, načtení modelu a inference syntetického obrázku
  (512 konečných hodnot). Rozpoznávání skutečných osob tím není ověřené.
  Při použití této cache je nutné před importem DeepFace nastavit
  `DEEPFACE_HOME` na cestu `edge/.venv` (v EDGE Pythonu `sys.prefix`).
  Nastavení bylo jen v kontrolním procesu; uživatelovy skripty se neměnily.
  Níže je zachovaný předchozí neúspěšný pokus o stažení.
- Kontrola společného `edge/.venv` dne 2026-10-08: všechny verze balíčků
  odpovídají `edge/requirements.txt`, `pip check` prošel, importy OpenCV,
  TensorFlow, tf-keras a DeepFace i jednoduchý výpočet TensorFlow prošly.
  Balíčky nebylo potřeba přeinstalovat. Chybějí váhy Facenet512; pokus stáhnout
  je do `edge/.venv/.deepface/weights` selhal na ověření HTTPS certifikátu.
  Následné stažení přes PowerShell mimo sandbox nebylo uživatelem povolené.
  Model proto zatím nebyl načtený ani otestovaný. `DEEPFACE_HOME` bylo při
  kontrole nastavené jen pro daný proces; trvalé umístění cache se neměnilo.
- Dne 2026-10-08 byla na zadání uživatele odstraněna automaticky vytvořená
  implementace demo_v001 včetně testů, návodu a cache modelů. Uživatel chce
  Python psát sám a dostávat vysvětlení a kód pouze v chatu po malých krocích.
  `edge/demo/demo_v001` obsahuje prázdný `visionDemo_V001.py`,
  `profiles.json` s prázdným seznamem profilů, prázdné zástupné soubory
  `video.mp4` a `target.jpg` a složku `faces/`. Média musí uživatel nahradit.
  Plán: více osob ve videu, 2–5 vhodných výřezů na profil, relativní cesty
  k výřezům v jednom JSON a volitelné hledání cíle. Zatím neimplementováno.
  Všechny demo vstupy a výstupy zůstávají v demo_v001; ostatní EDGE složky
  jsou pro finální projekt. Konfigurace spuštění `EDGE: demo v001` zůstává.
- Existují složky cameras, config, demo, output, storage, tests a vision.
- Existuje requirements.txt a lokální virtuální prostředí.
- Spustitelná lokální vision aplikace nyní existuje; viz záznam 2026-10-19 výše.
- requirements.txt obsahuje OpenCV, DeepFace 0.0.101, TensorFlow 2.21.0,
  tf-keras 2.21.0 a retina-face 0.0.18.
- Projekt je přesunutý do `C:\Users\matya\Desktop\PYTHON_VISION_DETECTOR`.
  Aktivační skripty, konfigurace a konzolové spouštěče obou virtualenv byly
  obnovené pro novou cestu. Neúplná instalace TensorFlow byla doplněná.
- Import DeepFace, OpenCV, TensorFlow a tf-keras prošel s `-X utf8`.
  Jednoduchý výpočet TensorFlow prošel; skutečné rozpoznávání a modelové
  váhy zatím nejsou ověřené.
- Dne 2026-10-01 byl do `edge/demo/demo_v000/visionDemo_V000.py` přidaný
  minimální RTSP test: URL z `CAMERA_RTSP_URL`, náhled OpenCV, hlášené
  rozlišení/FPS a ukončení klávesou Q. Bez vision pipeline a nových závislostí.
  Nativní diagnostika OpenCV/FFmpeg je vypnutá kvůli údajům v URL.
  Demo zůstává lokální a ignorované Gitem. Fyzické připojení Tapo C220
  zatím není ověřené; při přípravě nebyla proměnná s URL dostupná.
  V `edge/.venv` prošla kontrola syntaxe, import skriptu s OpenCV 5.0.0
  a kontrola srozumitelné chyby při chybějící proměnné.
  Pro spuštění tlačítkem v IDE demo načítá také lokální `.env` vedle skriptu
  pomocí již dostupného python-dotenv; proměnná prostředí má přednost.
  Cesta k `.env` nezávisí na pracovní složce. Přihlašovací údaje jsou mimo
  Python kód a `.env` je ignorovaný Gitem. Načtení konfigurace a importy
  byly ověřené bez připojení ke kameře.
- VS Code má výchozí interpreter `edge/.venv` a Windows spouštěcí konfiguraci
  `EDGE: kamera` s explicitním EDGE Pythonem pro F5 / Ctrl+F5. Již uložený
  výběr interpreteru ani aktivace v otevřeném terminálu se tím nemění.
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
Fyzicky ověřit implementovanou lokální RTSP pipeline v `edge/main.py`:
- vznik profilu, opakované rozpoznání i po restartu,
- postupné zlepšování vzorků a jejich počet v JSON i na disku,
- vhodnost prahů kvality/matchingu a odezvu na skutečné kameře.

Jednoduchý IoU tracking je implementovaný, fyzické ověření jeho omezení zůstává
součástí milníku. MP4/USB adaptéry a případné hledání cíle čekají na další zadání.

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
