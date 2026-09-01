import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Mail, Phone } from "lucide-react";
import AdminLayout from "../components/AdminLayout";
import { api, formatErr } from "../lib/api";

const TABS = [
  { key: "new", label: "Нови" },
  { key: "handled", label: "Обработени" },
  { key: "", label: "Всички" },
];

export default function AdminMessagesPage() {
  const [messages, setMessages] = useState([]);
  const [newCount, setNewCount] = useState(0);
  const [tab, setTab] = useState("new");

  const load = useCallback(() => {
    api.get("/admin/messages", { params: tab ? { status: tab } : {} })
      .then(({ data }) => { setMessages(data.messages); setNewCount(data.new_count); })
      .catch((e) => toast.error(formatErr(e)));
  }, [tab]);
  useEffect(() => { load(); }, [load]);

  const mark = async (m, status) => {
    try {
      await api.patch(`/admin/messages/${m.id}`, { status });
      toast.success(status === "handled" ? "Маркирано като обработено" : "Върнато като ново");
      load();
    } catch (e) { toast.error(formatErr(e)); }
  };

  return (
    <AdminLayout title="Запитвания">
      <div className="flex flex-wrap items-center gap-2 mb-5" data-testid="messages-tabs">
        {TABS.map((t) => (
          <button key={t.key || "all"} onClick={() => setTab(t.key)}
            className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
              tab === t.key ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-600 hover:border-slate-400"
            }`}
            data-testid={`messages-tab-${t.key || "all"}`}>
            {t.label}{t.key === "new" && newCount ? ` (${newCount})` : ""}
          </button>
        ))}
      </div>

      <div className="space-y-3" data-testid="messages-list">
        {messages.length === 0 && (
          <p className="bg-white border border-slate-200 rounded-xl p-6 text-sm text-slate-500 text-center">
            Няма запитвания.
          </p>
        )}
        {messages.map((m) => (
          <div key={m.id} className="bg-white border border-slate-200 rounded-xl p-4" data-testid={`message-${m.id}`}>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-bold text-slate-900">{m.name}</span>
              <span className="text-xs text-slate-500">{new Date(m.created_at).toLocaleString("bg-BG")}</span>
            </div>
            <p className="text-sm text-slate-600 mt-1 flex flex-wrap gap-x-4">
              <span className="inline-flex items-center gap-1"><Mail className="h-3.5 w-3.5" /> {m.email}</span>
              {m.phone && <span className="inline-flex items-center gap-1"><Phone className="h-3.5 w-3.5" /> {m.phone}</span>}
              <span className="text-slate-400 uppercase text-xs">{m.locale}</span>
            </p>
            <p className="text-sm text-slate-900 whitespace-pre-line mt-3 bg-slate-50 rounded-lg p-3">{m.message}</p>
            <div className="mt-3 flex items-center gap-3">
              {m.status === "new" ? (
                <button onClick={() => mark(m, "handled")}
                  className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-700 hover:text-emerald-900"
                  data-testid={`message-handle-${m.id}`}>
                  <Check className="h-4 w-4" /> Маркирай като обработено
                </button>
              ) : (
                <button onClick={() => mark(m, "new")}
                  className="text-sm text-slate-500 hover:text-slate-900" data-testid={`message-reopen-${m.id}`}>
                  Върни като ново
                </button>
              )}
              <a href={`mailto:${m.email}`} className="text-sm text-slate-500 hover:text-coral-700">Отговори</a>
            </div>
          </div>
        ))}
      </div>
    </AdminLayout>
  );
}
