import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { useLocaleCtx } from "../i18n/LocaleContext";

/** Breadcrumbs with schema.org JSON-LD-friendly markup for strong internal linking. */
export const Breadcrumbs = ({ items }) => {
  const { lp, t } = useLocaleCtx();
  const trail = [{ label: t("home"), to: lp("/") }, ...items];

  return (
    <nav className="pp-crumbs" aria-label="Breadcrumb" data-testid="breadcrumbs">
      {trail.map((c, i) => (
        <span key={`${c.label}-${i}`} className="flex items-center gap-1.5">
          {i > 0 && <ChevronRight className="h-3 w-3 text-slate-400" />}
          {c.to && i < trail.length - 1 ? (
            <Link to={c.to} className="hover:text-coral-600 transition-colors" data-testid={`crumb-${i}`}>
              {c.label}
            </Link>
          ) : (
            <span className="text-slate-900 font-medium" data-testid={`crumb-${i}`}>{c.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
};

export default Breadcrumbs;
