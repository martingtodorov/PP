import { useEffect, useRef, useState } from "react";
import { ShoppingBag } from "lucide-react";
import { fmtPrice, fmtBGN, showsBGN, img } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";

/**
 * Sticky buy bar — appears only once the main "Add to cart" button is scrolled out of view.
 * `anchorRef` points at the main CTA on the product page.
 */
export const StickyBuyBar = ({ product, variant, anchorRef, onAdd, soldOut }) => {
  const { t } = useLocaleCtx();
  const [visible, setVisible] = useState(false);
  const seen = useRef(true);

  useEffect(() => {
    const el = anchorRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        seen.current = entry.isIntersecting;
        setVisible(!entry.isIntersecting && entry.boundingClientRect.top < 0);
      },
      { threshold: 0 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [anchorRef, product?.handle]);

  if (!product || !variant) return null;
  const compare = variant.compare_at_eur || 0;

  return (
    <div className={`pp-buybar${visible ? " pp-buybar--in" : ""}`} data-testid="sticky-buy-bar" aria-hidden={!visible}>
      <div className="pp-buybar__inner">
        <img src={img(product.image, 160)} alt="" className="pp-buybar__img" />
        <div className="pp-buybar__meta">
          <span className="pp-buybar__title">{product.title}</span>
          <span className="pp-buybar__variant">{variant.name}</span>
        </div>
        <div className="pp-buybar__price">
          <span>{fmtPrice(variant.price_eur || 0)}</span>
          {compare > (variant.price_eur || 0) && <s className="pp-buybar__compare">{fmtPrice(compare)}</s>}
          {showsBGN() && <span className="pp-buybar__bgn">({fmtBGN(variant.price_eur || 0)})</span>}
        </div>
        <button type="button" onClick={onAdd} disabled={soldOut}
          className="pp-buybar__btn" aria-label={t("addToCart")} data-testid="sticky-add-to-cart">
          <ShoppingBag className="h-5 w-5" />
          <span className="pp-buybar__btn-text">{soldOut ? t("soldOut") : t("addToCart")}</span>
        </button>
      </div>
    </div>
  );
};

export default StickyBuyBar;
