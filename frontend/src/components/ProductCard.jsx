import { Link } from "react-router-dom";
import { fmtEUR, fmtBGN } from "../lib/api";
import { Badge } from "./ui/badge";

export default function ProductCard({ product }) {
  const minPrice = Math.min(...(product.variants || [{ price_eur: 0 }]).map((v) => v.price_eur));
  const totalStock = (product.variants || []).reduce((s, v) => s + (v.stock || 0), 0);
  const out = totalStock <= 0;
  return (
    <Link
      to={`/products/${product.handle}`}
      className="product-card group block bg-white border border-slate-200 rounded-xl overflow-hidden"
      data-testid={`product-card-${product.handle}`}
    >
      <div className="aspect-square bg-slate-50 overflow-hidden relative">
        <img
          src={product.image}
          alt={product.title}
          className="w-full h-full object-contain p-6 group-hover:scale-105 transition-transform duration-500"
          loading="lazy"
        />
        {out && (
          <span className="absolute top-3 left-3 bg-slate-900 text-white text-[10px] uppercase tracking-wider px-2 py-1 rounded">
            Изчерпано
          </span>
        )}
        {product.featured && !out && (
          <span className="absolute top-3 left-3 bg-blue-600 text-white text-[10px] uppercase tracking-wider px-2 py-1 rounded font-bold">
            Топ продукт
          </span>
        )}
      </div>
      <div className="p-5 border-t border-slate-100">
        {product.subtitle && (
          <p className="text-[10px] uppercase tracking-[0.18em] text-blue-600 font-bold mb-1.5">{product.subtitle}</p>
        )}
        <h3 className="font-display font-semibold text-slate-900 leading-snug line-clamp-2">{product.title}</h3>
        <div className="mt-3 flex items-baseline justify-between">
          <div>
            <span className="font-display font-bold text-slate-900 text-lg">{fmtEUR(minPrice)}</span>
            <span className="text-xs text-slate-500 ml-1.5">({fmtBGN(minPrice)})</span>
          </div>
          {(product.variants?.length || 0) > 1 && (
            <Badge variant="secondary" className="text-[10px]">от</Badge>
          )}
        </div>
      </div>
    </Link>
  );
}
