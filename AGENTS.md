# Pravidla projektu

## Kontext a komunikace
- Komunikuj s uživatelem česky.
- Jde o školní a portfolio projekt. Cílem je také pochopení systému.
- Před prací si přečti docs/PROJECT_STATE.md a prohlédni relevantní kód.
- Architektonický kontext a seznam budoucích funkcí nejsou zadáním k implementaci.
- Aktuální stav, omezení a rozhodnutí patří do docs/PROJECT_STATE.md.
- Při změně stavu aktualizuj tento dokument podle skutečně provedené práce.

## Způsob práce
- Implementuj postupně a pouze v rozsahu konkrétního zadání.
- Zachovávej fungující kód; preferuj malé, čitelné změny.
- Nevytvářej celý cílový systém najednou.
- Vysvětluj důležitá rozhodnutí a nové závislosti.
- Nepřidávej zbytečné abstrakce, služby ani infrastrukturu.
- Ověřuj změny přiměřeně jejich dopadu. Uváděj, co nebylo ověřeno.
- Netvrď výkon nebo funkčnost bez odpovídajícího ověření.

## Hranice aplikací
- frontend, backend a edge jsou samostatné aplikace.
- Nesdílejí aplikační kód přímými importy; komunikují přes API.
- Frontend poskytuje centrální webové rozhraní.
- Backend spravuje centrální data, identity, konfiguraci a komunikaci s edge.
- Výpočetně náročné zpracování videa probíhá primárně na edge.
- PostgreSQL je centrální zdroj pravdy; lokální edge úložiště slouží
  pro cache, lokální stav a neodeslané události.
- Stejná edge aplikace má podporovat více zařízení s vlastní identitou.

## Principy vision a synchronizace
- MP4, USB a RTSP mají používat společnou vision pipeline.
- Odděluj zdroj snímků od jejich zpracování.
- Tracking má bránit vytváření návštěvy pro každý jednotlivý snímek.
- Uchovávej vybrané užitečné vzorky, nikoli každý snímek.
- Rozlišuj časový offset videa a skutečný čas; historický čas vyžaduje
  známý začátek záznamu.
- Podobnost embeddingů neoznačuj jako pravděpodobnost.
- Synchronizaci navrhuj inkrementálně a počítej s výpadky připojení.
- Nepřenášej trvale plné kamerové streamy přes VPS bez konkrétní potřeby.
- Vzdálené příkazy musí být předem definované operace, nikoli libovolný shell.

## Data a soukromí
- Testuj s oprávněnými účastníky.
- Tajemství, biometrické snímky, embeddingy a testovací záznamy
  neukládej do veřejného Gitu.
- Z tváře nevyvozuj psychické vlastnosti, úmysly ani kriminalitu.
- Společný výskyt osob není důkaz osobního vztahu.

## Srozumitelnost infrastruktury
- Při změnách Dockeru vysvětli nové soubory, služby, volumes,
  síť, proměnné prostředí a rozdíl mezi image a kontejnerem.
- Nepřidávej Redis, message broker, Kubernetes, Traefik ani monitoring,
  pokud je nevyžaduje konkrétní zadání.
