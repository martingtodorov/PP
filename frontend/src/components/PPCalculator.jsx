import { useMemo, useState } from "react";
import { useLocaleCtx } from "../i18n/LocaleContext";

const formatNumber = (value, maximumDecimals) => Number(value.toFixed(maximumDecimals)).toString();

/** 1:1 port of the PurePeptide Shopify concentration calculator (mL / syringe units). */
export default function PPCalculator() {
  const { t } = useLocaleCtx();
  const [mg, setMg] = useState("5");
  const [ml, setMl] = useState("2");
  const [mcg, setMcg] = useState("250");
  const [unit, setUnit] = useState("ml");

  const drawMl = useMemo(() => {
    const peptideMg = parseFloat(mg);
    const volumeMl = parseFloat(ml);
    const doseMcg = parseFloat(mcg);
    if (
      !Number.isFinite(peptideMg) || !Number.isFinite(volumeMl) || !Number.isFinite(doseMcg) ||
      peptideMg <= 0 || volumeMl <= 0 || doseMcg <= 0
    ) return null;
    return (doseMcg * volumeMl) / (peptideMg * 1000);
  }, [mg, ml, mcg]);

  const value = drawMl === null ? "—" : unit === "units" ? formatNumber(drawMl * 100, 1) : formatNumber(drawMl, 3);
  const valueUnit = unit === "units" ? "units" : "mL";

  return (
    <div className="ppcalc" data-testid="pp-calculator">
      <div className="ppcalc__title">{t("calcTitle")}</div>

      <label>
        {t("calcMg")}
        <input type="number" step="1" inputMode="decimal" value={mg}
          onChange={(e) => setMg(e.target.value)} data-testid="calc-mg" />
      </label>
      <label>
        {t("calcMl")}
        <input type="number" step="0.1" inputMode="decimal" value={ml}
          onChange={(e) => setMl(e.target.value)} data-testid="calc-ml" />
      </label>
      <label>
        {t("calcMcg")}
        <input type="number" step="10" inputMode="decimal" value={mcg}
          onChange={(e) => setMcg(e.target.value)} data-testid="calc-mcg" />
      </label>

      <div className="ppcalc__unit-switch" role="group" aria-label="Result unit">
        <button type="button" className={`ppcalc__unit-button${unit === "ml" ? " is-active" : ""}`}
          aria-pressed={unit === "ml"} onClick={() => setUnit("ml")} data-testid="calc-unit-ml">
          mL
        </button>
        <button type="button" className={`ppcalc__unit-button${unit === "units" ? " is-active" : ""}`}
          aria-pressed={unit === "units"} onClick={() => setUnit("units")} data-testid="calc-unit-units">
          Units
        </button>
      </div>

      <div className="ppcalc__result">
        <div className="ppcalc__badge">{t("calcBadge")}</div>
        <div className="ppcalc__value">
          <span data-testid="calc-result">{value}</span> <span data-testid="calc-result-unit">{valueUnit}</span>
        </div>
      </div>

      <div className="ppcalc__conversion-note">1 mL = 100 units</div>
      <div className="ppcalc__note">{t("calcNote")}</div>
    </div>
  );
}
