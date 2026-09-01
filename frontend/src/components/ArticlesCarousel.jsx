import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { img } from "../lib/api";

/** Scrollable articles carousel — one row only, arrows on desktop, swipe on mobile. */
export default function ArticlesCarousel({ articles, lp }) {
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
  }, [articles.length]);

  const scrollBy = (dir) => {
    const el = trackRef.current;
    if (!el) return;
    const card = el.querySelector(".article-carousel__item");
    const step = card ? card.getBoundingClientRect().width + 12 : el.clientWidth * 0.6;
    el.scrollBy({ left: dir * step, behavior: "smooth" });
  };

  return (
    <div className="article-carousel" data-testid="articles-carousel">
      <button
        type="button"
        aria-label="Previous"
        className="collection-carousel__nav collection-carousel__nav--prev"
        onClick={() => scrollBy(-1)}
        disabled={!canPrev}
        data-testid="articles-carousel-prev"
      >
        <ArrowLeft className="h-4 w-4" />
      </button>
      <button
        type="button"
        aria-label="Next"
        className="collection-carousel__nav collection-carousel__nav--next"
        onClick={() => scrollBy(1)}
        disabled={!canNext}
        data-testid="articles-carousel-next"
      >
        <ArrowRight className="h-4 w-4" />
      </button>

      <div ref={trackRef} className="article-carousel__track">
        {articles.map((a) => (
          <div key={a.handle} className="article-carousel__item">
            <Link to={lp(`/articles/${a.handle}`)} className="article-card" data-testid={`article-${a.handle}`}>
              <div className="article-card__media"><img src={img(a.image, 480)} alt={a.title} loading="lazy" decoding="async" /></div>
              <h3 className="article-card__title">{a.title}</h3>
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
