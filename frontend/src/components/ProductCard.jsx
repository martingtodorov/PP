import { Link } from "react-router-dom";
import { fmtEUR, fmtBGN, showsBGN } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";

/** Port of the _product-list.liquid `products_grid` preset (gallery → title → price). */
export default function ProductCard({ product }) {
  const { lp, t } = useLocaleCtx();
  const variants = product.variants || [];
  const minPrice = variants.length ? Math.min(...variants.map((v) => v.price_eur)) : 0;
  const totalStock = variants.reduce((s, v) => s + (v.stock || 0), 0);
  const out = totalStock <= 0;
  const hasCompare = product.compare_at_price && product.compare_at_price > minPrice;

  const images = product.images && product.images.length ? product.images : [product.image];
  const primary = images[0];
  const alt = images[1] || images[0];
  const hasAlt = alt !== primary;

  return (
    <Link
      to={lp(`/products/${product.handle}`)}
      className={`product-card${hasAlt ? " product-card--has-alt" : ""}`}
      data-testid={`product-card-${product.handle}`}
      title={product.title}
    >
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
  );
}
