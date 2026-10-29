import { useApp } from '../state'
import { date, num } from '../format'

export function Methodology() {
  const { result } = useApp()
  const a = result?.assumptions ?? {}
  const pctOf = (k: string) => `${num(Number(a[k] ?? 0) * 100, 2)} %`
  return (
    <article className="prose">
      <h1>Předpoklady a metodika</h1>
      <p>
        Aplikace je rozhodovací podpora pro správce portfolia. Navrhuje obchody, ale nic neprovádí a nemění stav účtů.
        Všechna čísla počítá jeden společný výpočetní engine s přesnou desetinnou aritmetikou (zaokrouhluje se až
        při zobrazení); klienti se liší jen nastavením své strategie. Ocenění k {date(result?.valuation_date)}, verze modelu {result?.model_version}.
      </p>
      <h2>Ocenění a odchylky</h2>
      <p>
        Hodnota pozice = kusy × cena × kurz. Váhy se počítají z celkového majetku včetně hotovosti ve všech měnách (definice
        zadání). Toleranční pásmo složky je užší z absolutní tolerance (výchozí ±5 p. b.) a relativní tolerance (±25 % cílové váhy);
        akcie celkem (součet akciových instrumentů) mají vlastní pásmo (výchozí ±5 p. b.). Složka mimo pásmo spouští rebalancování; hranice se počítá bez zaokrouhlení.
      </p>
      <h2>Dvojí pohled: dnes a s ohledem na výběry</h2>
      <p>
        Každá složka se posuzuje (A) z dnešního celkového majetku a (B) z majetku po odečtení rezervy na výběry splatné do 90 dnů,
        a to ve všech kontrolních bodech šestiměsíčního horizontu (vklady, výběry, obchody, konec horizontu). Hotovost se v obou
        pohledech posuzuje po odečtení rezervy. Vklad je k dispozici až dnem připsání; nic se neprodává zbytečně dlouho dopředu –
        výběry za hranicí 90 dnů řeší podmíněné doplnění rezervy v době, kdy se k nim přiblíží.
      </p>
      <h2>Peníze v čase</h2>
      <ul>
        <li>Vypořádání obchodů T+2 pracovní dny (český kalendář svátků), převedená měna je k dispozici následující pracovní den.</li>
        <li>Výběr připadající na víkend nebo svátek musí být na účtu poslední pracovní den předtím; prodej pro výběr proto nejpozději 3 pracovní dny před ním.</li>
        <li>Tvrdé pravidlo: vypořádaná hotovost v žádné měně a žádný den neklesne pod nulu. Nevypořádané prodeje nelze vybrat.</li>
        <li>Když se obchoduje, zůstane na účtu minimální hotovost (výchozí 0,5 % majetku, aspoň 10 000 Kč) – i při cílové hotovosti 0 %, na poplatky a drobné výdaje; nákupy ji nepoužijí a po každém výběru zůstane v Kč.</li>
      </ul>
      <h2>Náklady a daně (modelové předpoklady)</h2>
      <ul>
        <li>Poplatek brokerovi {pctOf('commission_rate')} z objemu pokynu, minimum {String(a.commission_min ?? '10')} EUR/USD; jeden pokyn na instrument a den.</li>
        <li>Převod měn {pctOf('fx_cost')} jen z částky, která se skutečně převádí; existující zůstatky v měně se použijí přednostně.</li>
        <li>
          Fyzické osoby: časový test 3 roky (§ 4 odst. 1 písm. u) ZDP). Za datum nabytí se považuje vypořádání nákupu (nákup + 2 pracovní dny,
          GFŘ D-59), osvobozen je prodej až po uplynutí 3 let – <b>předpoklad k ověření u brokera</b>. Dále osvobození příjmů do
          100 000 Kč ročně, ztráty se započítávají v rámci roku, loty se prodávají metodou FIFO, nákupní cena v Kč dnešním kurzem
          (zjednodušení povolené zadáním). Odhad daně 15 %, citlivost 23 %.
        </li>
        <li>s.r.o.: daň závisí na účetní hodnotě, kterou data neobsahují – „nelze určit“; zobrazuje se jen podmíněný odhad 21 % ze zisku.</li>
      </ul>
      <h2>Jak vzniká doporučení</h2>
      <ol>
        <li>Engine vygeneruje varianty: bez obchodů, nyní (částečně do vnitřního pásma, nebo až na cíl), počkat na vklad, počkat na splnění časového testu.</li>
        <li>Každou variantu simuluje stejnými pravidly v peněžním deníku po dnech valuty, včetně podmíněných kroků (investice vkladu, doplnění rezervy).</li>
        <li>Pořadí: proveditelnost → dodržení pásem po dokončení → nejnižší celkové náklady (poplatky + převod měn + daň 15 %) → méně pokynů → menší objem → dřívější termín.</li>
        <li>Čekání vyhraje jen do 45 dnů, s odchylkou do 15 p. b., při úspoře aspoň max(10 000 Kč; 0,05 % majetku), která trvá i při dani 23 %.</li>
        <li>Pokud by doporučení změnila sazba 23 % nebo jiný výklad časového testu, stav je „Posoudit“ a zobrazí se obě varianty.</li>
        <li>Každý navržený pokyn nese štítky s pravidlem a čísly, které ho vyvolaly (pásmo, výběr, vklad, daň).</li>
      </ol>
      <h2>Stavy klientů</h2>
      <p>Opravit data, Zajistit likviditu do…, Posoudit, Provést nyní, Vyčkat do…, Zkontrolovat, Bez zásahu – v tomto pořadí naléhavosti.</p>
      <h2>Co model nezahrnuje</h2>
      <p>
        Budoucí ceny a kurzy (použijí se dnešní), spread a skluz, jiné příjmy a prodeje klienta v roce, historické nákupní poplatky,
        účetní hodnoty s.r.o., kalendáře burz, živé tržní ceny (napojí se novým adaptérem, výpočetní engine se nemění).
      </p>
    </article>
  )
}
