import { useState } from "react";
import { toast } from "sonner";
import { XCircle, Loader2 } from "lucide-react";
import { api, formatErr } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";

/* Customers may cancel while the parcel has not left the warehouse — the backend cancels the
   courier order, puts the stock back and mails both sides. */
export const CancelOrderButton = ({ order, onDone, className = "" }) => {
  const { t } = useLocaleCtx();
  const [busy, setBusy] = useState(false);
  if (!order?.cancellable) return null;

  const run = async () => {
    if (!window.confirm(t("cancelAsk"))) return;
    setBusy(true);
    try {
      await api.post(`/orders/${order.id}/cancel`, { reason: "" });
      toast.success(t("cancelDone"));
      onDone?.();
    } catch (e) {
      toast.error(formatErr(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      onClick={run}
      disabled={busy}
      className={`inline-flex items-center justify-center gap-2 border border-slate-300 hover:border-red-500 hover:text-red-600 text-slate-700 rounded-md px-5 py-2.5 text-sm font-semibold transition-colors disabled:opacity-60 ${className}`}
      data-testid="cancel-order-btn"
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
      {t("cancelOrder")}
    </button>
  );
};

export default CancelOrderButton;
