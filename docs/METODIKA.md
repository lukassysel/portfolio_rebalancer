# Metodika: pravidla, předpoklady a omezení

Podrobné vysvětlení pravidel. Krátký popis na jednu stranu je odevzdán zvlášť.

## K čemu nástroj je

Aplikace porovná dnešní složení portfolia každého klienta s jeho cílovou strategií. Spočítá několik možných postupů
(nic nedělat, obchodovat hned, počkat) a podle pevných pravidel doporučí ten nejvhodnější. „Nejvhodnější“ znamená
nejlepší z porovnávaných variant, ne optimum ze všech možných obchodů.

Výsledek je **návrh, ne pokyn**. O obchodu rozhoduje portfolio manažer, protože nástroj nezná všechno o klientovi ani
o trhu. Před zadáním pokynů manažer ověří aktuální ceny a hotovost, potvrdí s klientem termíny vkladů a výběrů a
u brokera zkontroluje data nákupu prodávaných lotů.

## Kdy zasáhnout

**Toleranční pásmo** je rozsah kolem cílové váhy, ve kterém se složka může volně pohybovat. Dokud je v pásmu,
neobchoduje se – malé odchylky nepředstavují velké riziko a obchodovat kvůli nim by stálo zbytečně na poplatcích
a případně na daních. Zásah přichází až při překročení pásma. Váhy se počítají z celého majetku včetně hotovosti.

**Šířka pásma** je menší ze dvou hodnot: ±5 procentních bodů, nebo ±25 % cílové váhy. U velké složky (cíl 60 %) by
25 % znamenalo povolit ±15 p. b., což je vůči celému portfoliu příliš – proto platí ±5 p. b. U malé složky (cíl 10 %)
by ±5 p. b. dovolilo ztratit polovinu složky – proto platí ±25 %, tedy ±2,5 p. b. Hranice mezi oběma případy je u cíle
20 %. Příklad: klient E má zlato 7,45 % při cíli 10 %. Absolutně jen −2,55 p. b., ale chybí mu čtvrtina zlata, které si
zvolil – a to už je mimo pásmo.

**Akcie celkem** (VWCE + AVWS) mají vlastní pásmo ±5 p. b. Když každý akciový fond zvlášť zůstane ve svém pásmu,
neznamená to, že je v pořádku i akciová část portfolia jako celek: oba fondy mohou mírně přerůst stejným směrem a akcií
dohromady je pak o téměř 10 p. b. víc, než klient chce. Podíl akcií je hlavní měřítko rizika portfolia.

**Nevyužitá hotovost.** Když má klient cíl hotovosti 0 %, chce mít peníze investované – hotovost na účtu nevydělává
podle jeho strategie. Úplná nula ale není možná: nakupují se jen celé kusy fondů a na poplatky je potřeba nechat
rezervu. Proto zasáhneme až tehdy, když hotovost přesáhne 5 % majetku.

**Proč pásma, a ne kalendář.** Pravidelné obchodování podle kalendáře by vyvolávalo obchody, i když se portfolio skoro
nepohnulo, a klient by zbytečně platil poplatky a daně. Nástroj se spouští pravidelně (např. každý měsíc s novými daty),
ale obchod navrhne jen tehdy, když je složka mimo pásmo, nebo když výběr nejde pokrýt bez prodeje.

**Pásmo není smluvní limit.** Pásmo je naše pravidlo pro zásah; pokud se tím výrazně ušetří, smí se krátce překročit
(viz čekání). Limity ze smlouvy s klientem nástroj nezná – pokud by byly přísnější, má přednost smlouva a manažer musí
obchod zadat hned.

## Dva pohledy

Každou složku kontrolujeme dvakrát: z celého majetku a po odečtení peněz na výběry splatné do 90 dní. Ty peníze klient
brzy vybere, takže by neměly zkreslovat složení zbytku portfolia a musí být připravené včas. Klient B je v pásmu
z celého majetku, ale po odečtení rezervy na výběry už ne. Kontrola platí pro dnešek i pro každý známý vklad a výběr
v příštích 6 měsících.

Rezerva kryje jen výběry do 90 dní. Vzdálenější výběry se do rezervy přidají, až se přiblíží – do té doby peníze
zůstávají investované a nečekají zbytečně na účtu.

## Kolik obchodovat

Složka mimo pásmo se nevrací přesně na cíl, ale do půli cesty mezi cílem a hranicí pásma (cíl ± polovina šířky
pásma). Příklad: cíl 60 %, pásmo 55–65 %, složka má 70 % – prodá se na 62,5 %, ne na 60 %. Obchoduje se tak méně a za nižší poplatky
a portfolio přitom nezůstane těsně u hranice, kde by ho malý pohyb cen znovu vyhodil z pásma. Pro srovnání se vždy
spočítá i varianta „až na cíl“ – částečná není automaticky levnější, protože poplatek má minimum za pokyn.

**Proč ne rovnou na cíl.** Návrat na cíl dává větší rezervu do další odchylky, ale prodá se víc kusů. U klientů bez daně
je rozdíl malý (A, B, D: 400–1 800 Kč) a obě cesty jsou obhajitelné. U fyzických osob ale rozhoduje daň: každý kus
prodaný navíc znamená daň ze zisku navíc, a kusy, které dnes neprodáme, mohou později projít tříletým časovým testem
a prodat se bez daně. U klienta E by návrat na cíl stál o 27 185 Kč víc, z toho asi 24 000 Kč daň.

- Obchoduje se v **celých kusech** (zlomky ETF broker neprodává).
- **Minimální obchod je 25 000 Kč** – menší by kvůli minimálnímu poplatku byl drahý a skoro nic by nezměnil.
- Peníze na nákup jdou nejdřív do **nejvíc podvážených složek**.
- Prodeje berou **nejstarší kusy jako první (FIFO)**, jak to dělají brokeři. U fyzických osob proto hlídáme, kdy daný
  lot projde tříletým časovým testem.
- **Známý vklad smí zmenšit prodej.** Polovina pásma se počítá pro majetek po vkladu, takže se neprodává zbytečně moc
  (jinak by se po vkladu muselo zase nakupovat). Dnes ale musí být složka aspoň v pásmu, i kdyby těsně u hranice –
  na samotný vklad nespoléháme. Klient A: VWCE se dnes prodá na 64,96 % (hranice 65 %), po vkladu 10. 11. klesne
  samo na 61,4 %.

## Peníze v čase

Peníze z prodeje přijdou až za 2 pracovní dny (T+2) a převedená měna je k dispozici o pracovní den později. Nástroj proto
sleduje hotovost den po dni a v každé měně zvlášť (český kalendář, bez víkendů a svátků): hotovost nikdy neklesne pod
nulu a peníze na výběr jsou na účtu včas. Vklad se počítá až od dne, kdy je připsaný.

Po obchodu zůstává na účtu minimální hotovost max(0,5 % majetku; 10 000 Kč), i když má klient cíl 0 % – zaplatí
poplatky a drobné výdaje, aby kvůli nim nebylo potřeba hned prodávat.

## Výběr varianty

Nástroj porovná až pět variant: nic nedělat · obchodovat hned do půli cesty k hranici · obchodovat hned až na cíl · počkat na
vklad · počkat na osvobození od daně. Každá se simuluje do konce šestiměsíčního horizontu.

Nejdřív vyřadí varianty, které nejdou provést (např. peníze na výběr by nebyly včas). Pak dá přednost těm, které vrátí
portfolio do pásma – to je smysl celého nástroje. Teprve mezi nimi vyhraje ta nejlevnější (poplatky + převod měn +
daň), při shodě ta s menším počtem pokynů, menším objemem a dřívějším termínem. Kdyby rozhodovala jen cena, vyhrálo by
vždy „nic nedělat“.

**Kdy se smí čekat.** Čekání je výjimka – portfolio po tu dobu zůstává mimo pásmo. Smí vyhrát, jen když:

- trvá nejvýš **45 dní** – déle už dnešní ceny nejsou spolehlivý předpoklad,
- odchylka nepřekročí **15 p. b.** – strop rizika, které klient mezitím nese,
- úspora je aspoň **max(10 000 Kč; 0,05 % majetku)** – kvůli pár stovkám nemá smysl zůstávat mimo pásmo,
- úspora vyjde **i při dani 23 %** – nesmí záviset na tom, jakou sazbu klient nakonec má.

Pokud by sazba 23 % nebo jiný výklad časového testu doporučení změnily, nástroj ukáže stav „Posoudit“ a rozhodne
manažer.

## Náklady a daně (zvolené předpoklady)

Poplatek 0,15 % z objemu, nejméně 10 EUR/USD za pokyn (jeden broker pro všechny). Převod měn 0,5 % jen z převáděné
částky; nejdřív se použije hotovost v dané měně.

**Fyzické osoby.**

- Zisk je osvobozen po **3 letech držení** (časový test), počítáno od vypořádání nákupu (nákup + 2 pracovní dny).
  Datum nabytí je předpoklad, který je třeba u brokera ověřit – nástroj ho u dotčeného lotu vždy vypíše.
- Osvobození, když **příjmy z prodeje** cenných papírů za rok nepřesáhnou 100 000 Kč. Předpokládáme, že spravujeme
  všechny cenné papíry klienta, proto ho počítáme jen z prodejů v tomto portfoliu.
- Ztráty se započítávají v rámci roku.
- Nákupní cena v Kč dnešním kurzem (zjednodušení povolené zadáním).
- Sazba 15 %, citlivost se počítá i při 23 %.

**s.r.o.** Zisk z prodeje se daní 21 % jako součást zisku firmy, bez časového testu a bez osvobození. Základem je účetní
hodnota cenných papírů, ne nákupní cena, a výsledná daň závisí i na ostatních výsledcích firmy (ztráty, ztráty minulých
let). Data zadání to neobsahují, proto nástroj ukáže daň jen podmíněně (21 % ze zisku proti nákupní ceně). V praxi by
stačilo doplnit účetní hodnotu pozic od účetní klienta.

## Co nástroj přidává

Jednoduché pravidlo „při překročení pásma hned vše na cíl“ by u dat zadání stálo **176 480 Kč a 20 pokynů**, náš návrh
**71 421 Kč a 17 pokynů**. Většinu rozdílu (asi 102 000 Kč) tvoří klient E, který počká necelý měsíc na osvobození od
daně – po tu dobu ale zůstane až 11,4 p. b. mimo cíl. U klienta A vyjde návrat do půli cesty k hranici levněji než na cíl,
u klienta B nástroj vidí blížící se výběr, u klienta C oba přístupy shodně nedělají nic. Jde o modelové náklady při
dnešních cenách, ne o zaručenou úsporu.

Ke každé odchylce nástroj ukáže, o kolik p. b. a Kč je za hranicí pásma, co to znamená pro riziko a kolik by klient
ztratil při poklesu akcií o 20 % (ilustrace, ne předpověď). Po měsíčním importu ukáže, co je mimo pásmo nově a co trvá.
Výsledek pro data zadání: [`SHRNUTI.md`](SHRNUTI.md).

## Co zatím neumí

- **Doplní se snadno** (nový vstup nebo adaptér, výpočet se nemění): živé ceny a napojení na brokera, účetní hodnoty
  s.r.o., dřívější prodeje v roce, kurzy ČNB k datu nákupu, spread jako další náklad, kalendáře burz.
- **S malou úpravou pravidel:** smluvní limity klienta – musely by zakázat čekání, to je nové pravidlo, ne jen údaj.
- **Nejde bez dat, která nemáme:** budoucí ceny a kurzy (nástroj počítá s dnešními), příčina odchylky a pásma podle
  volatility trhu (obojí potřebuje historii).

Čísla v datech zadání jsme neměnili. Jen v textové poznámce u klienta a v úvodním listu jsme vynechali název firmy.
