# Rebalancování klientských portfolií

Autor: Lukas Sysel

Webová aplikace v češtině pro portfolio manažera. Pro každého klienta ukáže, kde se portfolio odchyluje od cíle,
zda je potřeba zasáhnout, co přesně koupit a prodat (celé kusy), jak využít plánované vklady a výběry, kolik zásah
stojí (poplatky, převod měn, daň) a kdy je lepší počkat. Výstupem je **návrh, ne pokyn k obchodu**.

## Spuštění

| Systém | Postup |
|---|---|
| macOS / Linux | `git clone https://github.com/lukassysel/portfolio_rebalancer.git && cd portfolio_rebalancer && ./start.sh` |
| Windows | Code → Download ZIP, rozbalit, dvakrát kliknout na `start.bat` |
| Docker | `docker build -t rebalancer . && docker run -p 8000:8000 rebalancer` |

Aplikace se otevře na **http://localhost:8000** s pěti klienty ze zadání. První spuštění si samo stáhne Python
a knihovny (asi minutu). Ukončení: Ctrl+C.

## Jak to funguje

Data se čtou ze sešitu Excel ve formátu zadání (`docs/data_zadani.xlsx`): instrumenty a ceny,
kurzy, klienti s cílovými vahami, nákupní loty, hotovost a plánované vklady/výběry. Volitelný list *Strategie*
nastaví klientovi vlastní pravidla. Aplikace se otevře s daty zadání. Pro vyzkoušení nových výpočtů stačí upravit
klienty a strategie přímo v aplikaci – každá změna se hned přepočítá. Data se drží jen v prohlížeči: „Uložit data
(Excel)“ uloží vše do sešitu a „Načíst data (Excel)“ ho otevře znovu (tak se pokračuje v práci nebo se na další měsíc
načtou nové ceny, kurzy a pozice). Server nic neukládá.

Engine pro každého klienta:

1. ocení portfolio a porovná každou složku s tolerančním pásmem – z celého majetku i po odečtení rezervy na výběry
   do 90 dnů;
2. ověří po dnech, že hotovost pokryje každý výběr (vypořádání T+2, převod měn +1 pracovní den);
3. nasimuluje varianty – bez obchodů, nyní (částečně / až na cíl), počkat na vklad, počkat na osvobození od daně;
4. vybere variantu: proveditelná → drží pásma → nejlevnější → méně pokynů → menší objem → dřívější;
5. ověří, zda by doporučení změnila vyšší daň nebo jiný výklad časového testu.

Každý navržený pokyn nese **štítky s pravidlem a čísly**, proč vznikl – např. `VWCE +7,09 p. b. / ±5,00 p. b. po rezervě`,
`výběry 1. 11. 2026 – 15. 1. 2027 (4×) celkem 1 755 000 Kč`, `vklad 10. 11. 2026 600 000 Kč`. Štítků je pevný počet podle pravidel, ne podle klientů – nový klient s jinou strategií dostane
stejné štítky s vlastními čísly. Kontroly, které o doporučení rozhodly, jsou na stránce klienta sbalené pod „Záznam rozhodnutí“.

U každé odchylky aplikace ukáže, **co znamená**: o kolik p. b. a Kč je složka za hranicí pásma (ne jen od cíle), co to
dělá s rizikem a kolik by portfolio ztratilo při poklesu akcií o 20 % dnes, při cíli a po návrhu. Přehled navíc
**srovnává doporučení s jednoduchým pravidlem** „při překročení hned vše na cíl“ – náklady, počet pokynů a v čem se liší.
Po načtení dat dalšího měsíce ukáže u každého klienta, co je **mimo pásmo nově a co trvá**, a zda se změnily vstupy klienta,
nebo jen ceny. Vyzkoušet: „Načíst data (Excel)“ → [`docs/priklad_dalsi_mesic.xlsx`](docs/priklad_dalsi_mesic.xlsx)
(smyšlený 23. 11. 2026: akcie +6–7 %, dluhopisy −2 %, zlato −15 %, vklad A a renta B proběhly, návrhy z října neprovedeny).

Pravidla a předpoklady s vysvětlením: [`docs/METODIKA.md`](docs/METODIKA.md). Co se má stát u pěti klientů ze
zadání a proč: [`docs/SHRNUTI.md`](docs/SHRNUTI.md).

## Modulární stavba

Výpočetní engine (`rebalancer/engine`) je čistý Python bez vstupů/výstupů: dostane data a strategie, vrátí výsledek.
Nezná Excel ani web – ty jsou jen adaptéry kolem něj. Stejná data dají vždy stejný výsledek a každá změna se ověří
automatickými testy (`uv run pytest -q`).

Co to přináší:

- **Noví klienti a strategie** – v aplikaci nebo v Excelu; **nové tickery a měny** – v Excelu (listy Instrumenty a
  Kurzy). Žádná změna kódu.
- **Nové pravidlo** (např. limit jedné pozice) – jedna kontrola v enginu, jeden parametr strategie a jeden štítek;
  zbytek systému se nemění.
- **Reálná data** – ano: živé ceny a kurzy (API poskytovatele tržních dat, kurzy ČNB) nebo výpisy pozic od brokera
  se napojí novým adaptérem vedle čtečky Excelu. Engine se nemění.
- **Jiný systém** (CRM, portál) – volá engine přímo (`rebalancer.engine.evaluate`) nebo přes webové API
  (`/api/evaluate`).

## Rozsah této verze

Verze je postavená a ověřená na **ukázkových datech ze zadání** (5 fiktivních klientů, 4 ETF, 3 měny, statické ceny
k 23. 10. 2026). Pravidla jsou obecná, ale z tak malého vzorku nelze ověřit každý scénář z praxe (dividendy, kupony,
více účtů jednoho klienta, jiné daňové situace). Ty se doplní rozšířením podle předchozí části.

## Struktura

```
rebalancer/engine/    výpočetní engine (pravidla, simulace, štítky)
rebalancer/adapters/  čtení a zápis Excelu
rebalancer/api/       webové API, servíruje i aplikaci
rebalancer/cli/       příkazová řádka nad stejným enginem
web/                  webové rozhraní (React; web/dist = sestavená verze)
tests/                automatické testy
docs/                 zadání, data zadání, metodika, výstup pro data zadání
```
