import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import ProductCard from "./ProductCard";

/**
 * Sliding products carousel — same nav pattern as CollectionsCarousel.
 * Uses container queries (mobile_card_size: 60cqw on mobile, columns: 4 desktop).
 * icons_style: arrow, icons_shape: circle (per `_product-list.liquid` carousel preset).
 */
export default function ProductsCarousel({ products }) {
  const trackRef = useRef(null);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(true);

  const checkBounds = () => {
    const el = trackRef.current;
    if (!el) return;
    setCanPrev(el.scrollLeft > 4);
    setCanNext(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  };

  useEffect(() => {
    checkBounds();
    const el = trackRef.current;
    if (!el) return;
    el.addEventListener("scroll", checkBounds, { passive: true });
    window.addEventListener("resize", checkBounds);
    return () => {
      el.removeEventListener("scroll", checkBounds);
      window.removeEventListener("resize", checkBounds);
    };
  }, [products.length]);

  const scrollBy = (dir) => {
    const el = trackRef.current;
    if (!el) return;
    const card = el.querySelector(".product-carousel__item");
    const step = card ? card.getBoundingClientRect().width + 8 : el.clientWidth * 0.6;
    el.scrollBy({ left: dir * step, behavior: "smooth" });
  };

  return (
    <div className="product-carousel" data-testid="products-carousel">
      <button
        type="button"
        aria-label="Previous"
        className="collection-carousel__nav collection-carousel__nav--prev"
        onClick={() => scrollBy(-1)}
        disabled={!canPrev}
        data-testid="products-carousel-prev"
      >
        <ArrowLeft className="h-4 w-4" />
      </button>
      <button
        type="button"
        aria-label="Next"
        className="collection-carousel__nav collection-carousel__nav--next"
        onClick={() => scrollBy(1)}
        disabled={!canNext}
        data-testid="products-carousel-next"
      >
        <ArrowRight className="h-4 w-4" />
      </button>

      <div ref={trackRef} className="product-carousel__track">
        {products.map((p) => (
          <div key={p.id} className="product-carousel__item">
            <ProductCard product={p} />
          </div>
        ))}
      </div>
    </div>
  );
}
