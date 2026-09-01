import { Link } from "react-router-dom";
import { toast } from "sonner";
import { fmtEUR, fmtBGN, showsBGN } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { useCart } from "../context/CartContext";

/** Port of the _product-list.liquid `products_grid` preset (gallery → title → price). */
export default function ProductCard({ product, showAddToCart = false }) {
  const { lp, t } = useLocaleCtx();
  const { add } = useCart();
  const variants = product.variants || [];
  const minPrice = variants.length ? Math.min(...variants.map((v) => v.price_eur)) : 0;
  const totalStock = variants.reduce((s, v) => s + (v.stock || 0), 0);
  const out = totalStock <= 0;
  const hasCompare = product.compare_at_price && product.compare_at_price > minPrice;

  const images = product.images && product.images.length ? product.images : [product.image];
  const primary = images[0];
  const alt = images[1] || images[0];
  const hasAlt = alt !== primary;

  const quickAdd = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const variant = variants.find((v) => (v.stock || 0) > 0) || variants[0];
    if (!variant) return;
    add(product, variant, 1);
    toast.success(t("addToCart"), { description: `${product.title}${variant.name ? ` — ${variant.name}` : ""}` });
  };

  return (
    <div
      className={`product-card${hasAlt ? " product-card--has-alt" : ""}`}
      data-testid={`product-card-${product.handle}`}
    >
      <Link to={lp(`/products/${product.handle}`)} className="product-card__link" title={product.title}>
        <div className="product-card__media">
          <img src={primary} alt={product.title} className="product-card__image product-card__image--primary" loading="lazy" />
          {hasAlt && (
            <img src={alt} alt="" className="product-card__image product-card__image--alt" loading="lazy" aria-hidden="true" />
          )}
          <div className="product-badges product-badges--top-left">
            {hasCompare && !out && (
              <span className="product-badges__badge product-badges__badge--rectangle product-badges__badge--sale">%</span>
            )}
          </div>
          {out && (
            <div className="product-badges product-badges--top-right">
              <span className="product-badges__badge product-badges__badge--rectangle product-badges__badge--soldout">
                {t("soldOut")}
              </span>
            </div>
          )}
        </div>

        <h3 className="product-card__title">{product.title}</h3>

        <div className="product-card__price">
          {variants.length > 1 && <span className="text-slate-500 mr-1">{t("from")}</span>}
          <span>{fmtEUR(minPrice)}</span>
          {showsBGN() && <span className="text-slate-500 ml-1.5 text-[12px]">({fmtBGN(minPrice)})</span>}
        </div>
      </Link>

      {showAddToCart && (
        <button type="button" onClick={quickAdd} disabled={out}
          className="product-card__add bg-coral-600 hover:bg-coral-700 disabled:bg-slate-300 text-white"
          data-testid={`quick-add-${product.handle}`}>
          {out ? t("soldOut") : t("addToCart")}
        </button>
      )}
    </div>
  );
}
