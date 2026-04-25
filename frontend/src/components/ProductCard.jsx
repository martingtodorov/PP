import { Link } from "react-router-dom";
import { toast } from "sonner";
import { fmtEUR, fmtBGN } from "../lib/api";
import { useCart } from "../context/CartContext";

/**
 * Port of Shopify _product-card.liquid + _product-card-gallery.liquid
 * - corner badges (sale / sold-out / featured) at top-left or top-right
 * - hover swaps to second product image when available (gallery effect)
 * - quick-add button overlay on hover (adds first available variant)
 * - title + min-price meta below image (zoomed-out grid view)
 */
export default function ProductCard({ product }) {
  const { add } = useCart();
  const variants = product.variants || [];
  const minPrice = variants.length ? Math.min(...variants.map((v) => v.price_eur)) : 0;
  const totalStock = variants.reduce((s, v) => s + (v.stock || 0), 0);
  const out = totalStock <= 0;
  const hasCompare = product.compare_at_price && product.compare_at_price > minPrice;

  const images = product.images && product.images.length ? product.images : [product.image];
  const primary = images[0];
  const alt = images[1] || images[0];

  const firstAvailable = variants.find((v) => (v.stock || 0) > 0) || variants[0];

  const onQuickAdd = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!firstAvailable || out) return;
    add(product, firstAvailable, 1);
    toast.success("Добавено в количката", { description: `${product.title} — ${firstAvailable.name}` });
  };

  return (
    <Link
      to={`/products/${product.handle}`}
      className="product-card"
      data-testid={`product-card-${product.handle}`}
    >
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

        {/* Top-left badges (Sale / Featured) */}
        <div className="product-badges product-badges--top-left">
          {hasCompare && !out && (
            <span className="product-badges__badge product-badges__badge--rectangle product-badges__badge--sale">
              Промоция
            </span>
          )}
          {product.featured && !out && !hasCompare && (
            <span className="product-badges__badge product-badges__badge--rectangle">
              Топ
            </span>
          )}
        </div>

        {/* Top-right: sold out */}
        {out && (
          <div className="product-badges product-badges--top-right">
            <span className="product-badges__badge product-badges__badge--rectangle product-badges__badge--soldout">
              Изчерпано
            </span>
          </div>
        )}

        {/* Quick add overlay (hover) */}
        <button
          type="button"
          className="product-card__quick-add"
          onClick={onQuickAdd}
          disabled={out || !firstAvailable}
          data-testid={`quick-add-${product.handle}`}
        >
          {out ? "Изчерпано" : `Бързо добавяне${variants.length > 1 ? " — " + firstAvailable.name : ""}`}
        </button>
      </div>

      <div className="product-card__meta">
        {product.subtitle && (
          <p className="text-[10px] uppercase tracking-[0.18em] text-coral-600 font-bold">{product.subtitle}</p>
        )}
        <h3 className="product-card__title">{product.title}</h3>
        <div className="product-card__price">
          {variants.length > 1 && <span className="text-slate-500 text-xs mr-1">от</span>}
          <span className="font-semibold">{fmtEUR(minPrice)}</span>
          <span className="text-slate-500 text-xs ml-1.5">({fmtBGN(minPrice)})</span>
        </div>
      </div>
    </Link>
  );
}
