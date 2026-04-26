import { useMemo, useState } from "react";

/**
 * Faithful React port of the supplied `_pp-calculator.liquid` snippet.
 * Markup, class names, default values, formula and CSS preserved verbatim.
 *   drawMl = (doseMcg * volumeMl) / (peptideMg * 1000)
 *   defaults: mg=5, ml=2, mcg=250
 */
export default function PPCalculator() {
  const [mg, setMg] = useState("5");
  const [ml, setMl] = useState("2");
  const [mcg, setMcg] = useState("250");

  const result = useMemo(() => {
    const peptideMg = parseFloat(mg);
    const volumeMl = parseFloat(ml);
    const doseMcg = parseFloat(mcg);
    if (peptideMg > 0 && volumeMl > 0 && doseMcg > 0) {
      const drawMl = (doseMcg * volumeMl) / (peptideMg * 1000);
      return Number(drawMl.toFixed(3)).toString();
    }
    return "—";
  }, [mg, ml, mcg]);

  return (
    <div className="ppcalc" data-testid="pp-calculator">
      <div className="ppcalc__title">Калкулатор за концентрация на пептиди</div>

      <label>
        Количество пептид (mg)
        <input
          id="mg"
          type="number"
          step="1"
          inputMode="numeric"
          value={mg}
          onChange={(e) => setMg(e.target.value)}
          data-testid="calc-mg"
        />
      </label>

      <label>
        Обем разтвор (mL)
        <input
          id="ml"
          type="number"
          step="1"
          inputMode="numeric"
          value={ml}
          onChange={(e) => setMl(e.target.value)}
          data-testid="calc-ml"
        />
      </label>

      <label>
        Желана доза (mcg)
        <input
          id="mcg"
          type="number"
          step="10"
          inputMode="numeric"
          value={mcg}
          onChange={(e) => setMcg(e.target.value)}
          data-testid="calc-mcg"
        />
      </label>

      <div className="ppcalc__result">
        <div className="ppcalc__badge">Необходим обем</div>
        <div className="ppcalc__value">
          <span id="result" data-testid="calc-result">{result}</span> mL
        </div>
      </div>

      <div className="ppcalc__note">
        За научни и лабораторни цели. Изчислението е ориентировъчно.
      </div>
    </div>
  );
}
