import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Bell, BellOff, Send, Smartphone } from "lucide-react";
import { api, formatErr } from "../lib/api";
import { currentSubscription, isIOS, isStandalone, pushSupported, subscribeAdmin, unsubscribeAdmin } from "../lib/push";

export const PushOptIn = () => {
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState({ subscriptions: [], log: [] });

  const refresh = useCallback(async () => {
    const sub = await currentSubscription().catch(() => null);
    setEnabled(!!sub);
    api.get("/admin/push/status").then(({ data }) => setStatus(data)).catch(() => {});
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const toggle = async () => {
    setBusy(true);
    try {
      if (enabled) {
        await unsubscribeAdmin();
        toast.success("Нотификациите са изключени на това устройство");
      } else {
        await subscribeAdmin();
        toast.success("Нотификациите са включени на това устройство");
      }
      await refresh();
    } catch (e) { toast.error(e.message || formatErr(e)); } finally { setBusy(false); }
  };

  const test = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/admin/push/test");
      toast.success(`Изпратена тестова нотификация до ${data.sent} устройство(а)`);
      refresh();
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  const needsHomeScreen = isIOS() && !isStandalone();

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5" data-testid="push-optin-card">
      <h2 className="font-display font-bold text-slate-900 flex items-center gap-2">
        <Bell className="h-4 w-4" /> Push нотификации за нови поръчки
      </h2>
      <p className="text-sm text-slate-500 mt-1">
        Получавай известие на този телефон/компютър при всяка нова поръчка и всяко запитване от формата за контакт.
      </p>

      {!pushSupported() && (
        <p className="text-sm text-amber-700 mt-3">Този браузър не поддържа push нотификации.</p>
      )}

      {needsHomeScreen && (
        <div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-900 flex gap-2"
          data-testid="push-ios-hint">
          <Smartphone className="h-4 w-4 mt-0.5 flex-shrink-0" />
          <span>
            На iPhone: <strong>Share → Add to Home Screen</strong>, отвори сайта от новата икона и после включи нотификациите.
          </span>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 mt-4">
        <button onClick={toggle} disabled={busy || !pushSupported()}
          className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-md text-sm font-semibold disabled:opacity-50 ${
            enabled ? "border border-slate-300 hover:border-slate-900" : "bg-coral-600 hover:bg-coral-700 text-white"
          }`}
          data-testid="push-toggle-btn">
          {enabled ? <><BellOff className="h-4 w-4" /> Изключи на това устройство</> : <><Bell className="h-4 w-4" /> Включи нотификации</>}
        </button>
        <button onClick={test} disabled={busy || !status.subscriptions?.length}
          className="inline-flex items-center gap-2 border border-slate-300 hover:border-slate-900 px-4 py-2.5 rounded-md text-sm font-semibold disabled:opacity-50"
          data-testid="push-test-btn">
          <Send className="h-4 w-4" /> Тестова нотификация
        </button>
        <span className="text-xs text-slate-500" data-testid="push-device-count">
          Активни устройства: {status.subscriptions?.length || 0}
        </span>
      </div>

      {status.log?.length > 0 && (
        <ul className="mt-4 text-xs text-slate-500 space-y-1" data-testid="push-log">
          {status.log.slice(0, 5).map((l) => (
            <li key={l.id}>
              {new Date(l.at).toLocaleString("bg-BG")} · {l.title} · изпратени {l.sent}
              {l.failed ? `, неуспешни ${l.failed}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
