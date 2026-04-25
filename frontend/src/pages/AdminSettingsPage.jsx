import { useEffect, useState } from "react";
import { toast } from "sonner";
import AdminLayout from "../components/AdminLayout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { api, formatErr } from "../lib/api";

export default function AdminSettingsPage() {
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get("/settings").then(({ data }) => setS(data)); }, []);

  const save = async () => {
    setBusy(true);
    try { await api.put("/admin/settings", { value: s }); toast.success("Запазено"); }
    catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  if (!s) return <AdminLayout title="Настройки"><div className="text-slate-500">Зареждане…</div></AdminLayout>;
  const set = (k, v) => setS({ ...s, [k]: v });

  return (
    <AdminLayout title="Настройки">
      <div className="max-w-3xl bg-white border border-slate-200 rounded-xl p-8 space-y-5">
        <div><Label>Име на сайта</Label><Input value={s.site_name || ""} onChange={(e) => set("site_name", e.target.value)} data-testid="set-site_name" /></div>
        <div><Label>Слоган</Label><Input value={s.tagline || ""} onChange={(e) => set("tagline", e.target.value)} /></div>
        <div><Label>Заглавие на хероя</Label><Input value={s.hero_title || ""} onChange={(e) => set("hero_title", e.target.value)} /></div>
        <div><Label>Подзаглавие на хероя</Label><Textarea rows={3} value={s.hero_subtitle || ""} onChange={(e) => set("hero_subtitle", e.target.value)} /></div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div><Label>Главен бутон</Label><Input value={s.hero_cta_primary || ""} onChange={(e) => set("hero_cta_primary", e.target.value)} /></div>
          <div><Label>Втори бутон</Label><Input value={s.hero_cta_secondary || ""} onChange={(e) => set("hero_cta_secondary", e.target.value)} /></div>
        </div>
        <div><Label>Лента с обявление</Label><Input value={s.announcement || ""} onChange={(e) => set("announcement", e.target.value)} /></div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div><Label>Имейл за контакт</Label><Input value={s.contact_email || ""} onChange={(e) => set("contact_email", e.target.value)} /></div>
          <div><Label>Телефон</Label><Input value={s.contact_phone || ""} onChange={(e) => set("contact_phone", e.target.value)} /></div>
        </div>
        <div><Label>Текст за футъра</Label><Textarea rows={2} value={s.footer_text || ""} onChange={(e) => set("footer_text", e.target.value)} /></div>
        <Button onClick={save} disabled={busy} className="bg-coral-600 hover:bg-coral-700" data-testid="settings-save-btn">{busy ? "…" : "Запази"}</Button>
      </div>
    </AdminLayout>
  );
}
