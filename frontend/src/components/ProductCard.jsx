import { Link } from "react-router-dom";
import { fmtEUR, fmtBGN } from "../lib/api";

/**
 * Faithful port of the _product-list.liquid `products_grid` preset
 * `static-product-card` block_order = [product-card-gallery, product_title, price]
 *
 * Matched settings:
 *   product_card_gap: 4               → 4px column-gap between gallery / title / price
 *   product-card-gallery.image_ratio: adapt
 *   product_title.font_size: 1rem, alignment: left, color: var(--color-foreground)
 *   price.font_size: 1rem,        alignment: left, type_preset: h6, color: var(--color-foreground)
 *   _product-card-gallery: hover swaps to second image
 */
export default function ProductCard({ product }) {
  const variants = product.variants || [];
  const minPrice = variants.length ? Math.min(...variants.map((v) => v.price_eur)) : 0;
  const totalStock = variants.reduce((s, v) => s + (v.stock || 0), 0);
  const out = totalStock <= 0;
  const hasCompare = product.compare_at_price && product.compare_at_price > minPrice;

  const images = product.images && product.images.length ? product.images : [product.image];
  const primary = images[0];
  const alt = images[1] || images[0];

  return (
    <Link
      to={`/products/${product.handle}`}
      className="product-card"
      data-testid={`product-card-${product.handle}`}
    >
      {/* product-card-gallery */}
      <div className="product-card__media">
        <img
          src={primary}
          alt={product.title}
          className="product-card__image product-card__image--primary"
          loading="lazy"
        />
        {alt !== primary && (
          <img
            src={alt}
            alt=""
            className="product-card__image product-card__image--alt"
            loading="lazy"
            aria-hidden="true"
          />
        )}

        {/* product-badges (top-left for sale, top-right for sold-out) */}
        <div className="product-badges product-badges--top-left">
          {hasCompare && !out && (
            <span className="product-badges__badge product-badges__badge--rectangle product-badges__badge--sale">
              Промоция
            </span>
          )}
        </div>
        {out && (
          <div className="product-badges product-badges--top-right">
            <span className="product-badges__badge product-badges__badge--rectangle product-badges__badge--soldout">
              Изчерпано
            </span>
          </div>
        )}
      </div>

      {/* product-title — alignment: left, font-size: 1rem */}
      <h3 className="product-card__title">{product.title}</h3>

      {/* price — alignment: left, font-size: 1rem, h6 preset */}
      <div className="product-card__price">
        {variants.length > 1 && <span className="text-slate-500 mr-1">от</span>}
        <span>{fmtEUR(minPrice)}</span>
        <span className="text-slate-500 ml-1.5 text-[12px]">({fmtBGN(minPrice)})</span>
      </div>
    </Link>
  );
}
