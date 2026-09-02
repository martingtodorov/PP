/**
 * Storefront pricing. Products are priced in EUR; the CZ/HU/PL/RO storefronts are shown and charged
 * in their own currency, converted with the daily ECB rate the API hands us and rounded up to a
 * psychological price. The rounding rule mirrors backend/currency.py — keep the two in sync.
 */
let fx = { currency: "EUR", rate: 1, intl_locale: "bg-BG", date: null };

export const setFx = (data) => {
  fx = { ...fx, ...(data || {}) };
};

export const currencyCode = () => fx.currency;
export const isLocalCurrency = () => fx.currency !== "EUR";

export const nicePrice = (eur, rate = fx.rate) => {
  const raw = (Number(eur) || 0) * (Number(rate) || 0);
  if (raw <= 0) return 0;
  if (raw < 100) return Math.ceil(raw);
  if (raw < 1000) return Math.ceil((raw + 1) / 10) * 10 - 1;
  return Math.ceil((raw + 10) / 100) * 100 - 10;
};

export const fmtPrice = (eur) => fmtAmount(amountOf(eur));

/** Display amount for one EUR price: rounded once, in the storefront currency. */
export const amountOf = (eur) =>
  fx.currency === "EUR" ? Math.round((Number(eur) || 0) * 100) / 100 : nicePrice(eur);

/** Plain conversion (no psychological rounding) — used for fixed-amount discounts. */
export const convertPlain = (eur) =>
  fx.currency === "EUR" ? Math.round((Number(eur) || 0) * 100) / 100
    : Math.round((Number(eur) || 0) * fx.rate);

export const fmtAmount = (amount) => {
  if (fx.currency === "EUR") {
    return new Intl.NumberFormat("bg-BG", { style: "currency", currency: "EUR" }).format(Number(amount) || 0);
  }
  return new Intl.NumberFormat(fx.intl_locale || "en-GB", {
    style: "currency",
    currency: fx.currency,
    maximumFractionDigits: 0,
  }).format(Number(amount) || 0);
};

/**
 * Cart/checkout arithmetic in the display currency. Totals must be built from the already rounded
 * line prices — mirrors order_amounts() in backend/currency.py, otherwise the cart and the recorded
 * order disagree (349 vs 351 lei).
 */
export const cartAmounts = ({ items = [], shippingEur = 0, discount = null }) => {
  const lines = items.map((it) => amountOf(it.price_eur) * (it.quantity || 1));
  const subtotal = lines.reduce((sum, line) => sum + line, 0);
  const shipping = shippingEur ? amountOf(shippingEur) : 0;
  let discountAmount = 0;
  if (discount) {
    discountAmount = discount.type === "percent"
      ? (fx.currency === "EUR"
        ? Math.round(subtotal * (Number(discount.value) || 0)) / 100
        : Math.round(subtotal * (Number(discount.value) || 0) / 100))
      : convertPlain(discount.discount_eur || 0);
    discountAmount = Math.min(discountAmount, subtotal);
  }
  return { lines, subtotal, shipping, discountAmount,
           total: Math.max(subtotal - discountAmount, 0) + shipping };
};
