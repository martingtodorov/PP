import { useEffect, useState } from "react";
import { toast } from "sonner";
import AdminLayout from "../components/AdminLayout";
import { PushOptIn } from "../components/PushOptIn";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { api, formatErr } from "../lib/api";

export default function AdminSettingsPage() {
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);

  const [testTo, setTestTo] = useState("");

  useEffect(() => { api.get("/admin/settings").then(({ data }) => setS(data.settings)); }, []);

  const sendTest = async () => {
    setBusy(true);
    try { await api.post("/admin/email/test", { to: testTo }); toast.success("Тестовият имейл е изпратен"); }
    catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  const save = async () => {
    setBusy(true);
    try { await api.put("/admin/settings", { value: s }); toast.success("Запазено"); }
    catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  if (!s) return <AdminLayout title="Настройки"><div className="text-slate-500">Зареждане…</div></AdminLayout>;
  const set = (k, v) => setS({ ...s, [k]: v });

  return (
    <AdminLayout title="Настройки">
      <div className="max-w-3xl mb-6"><PushOptIn /></div>
      <div className="max-w-3xl bg-white border border-slate-200 rounded-xl p-8 space-y-5">
        <div><Label>Име на сайта</Label><Input value={s.site_name || ""} onChange={(e) => set("site_name", e.target.value)} data-testid="set-site_name" /></div>
        <div><Label>Слоган</Label><Input value={s.tagline || ""} onChange={(e) => set("tagline", e.target.value)} /></div>
        <div><Label>Заглавие на хероя</Label><Input value={s.hero_title || ""} onChange={(e) => set("hero_title", e.target.value)} /></div>
        <div><Label>Подзаглавие на хероя</Label><Textarea rows={3} value={s.hero_subtitle || ""} onChange={(e) => set("hero_subtitle", e.target.value)} /></div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div><Label>Главен бутон</Label><Input value={s.hero_cta_primary || ""} onChange={(e) => set("hero_cta_primary", e.target.value)} /></div>
          <div><Label>Втори бутон</Label><Input value={s.hero_cta_secondary || ""} onChange={(e) => set("hero_cta_secondary", e.target.value)} /></div>
        </div>
        <div>
          <Label>Съобщения в горната лента (по едно на ред)</Label>
          <Textarea rows={3} value={(s.announcements || []).join("\n")}
            onChange={(e) => set("announcements", e.target.value.split("\n").filter(Boolean))}
            data-testid="set-announcements" />
        </div>

        <div className="border-t border-slate-200 pt-5">
          <h2 className="font-bold text-slate-900 mb-3">Имейли (Resend)</h2>
          <div className="space-y-4">
            <div>
              <Label>Resend API ключ</Label>
              <Input type="password" placeholder="re_..." value={s.resend_api_key || ""}
                onChange={(e) => set("resend_api_key", e.target.value)} data-testid="set-resend-key" />
              <p className="text-xs text-slate-500 mt-1">Създайте ключ в resend.com → API Keys. Записва се защитено и не се излъчва публично.</p>
            </div>
            <div>
              <Label>Изпращач (From)</Label>
              <Input placeholder="PurePeptide &lt;orders@purepeptide.bg&gt;" value={s.resend_from || ""}
                onChange={(e) => set("resend_from", e.target.value)} data-testid="set-resend-from" />
            </div>
            <div className="flex gap-2 items-end">
              <div className="flex-1"><Label>Тестов имейл до</Label><Input value={testTo} onChange={(e) => setTestTo(e.target.value)} data-testid="test-email-input" /></div>
              <Button type="button" variant="outline" onClick={sendTest} disabled={busy || !testTo} data-testid="test-email-btn">Изпрати тест</Button>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-200 pt-5">
          <h2 className="font-bold text-slate-900 mb-3">Банкова сметка (за банков превод)</h2>
          <p className="text-xs text-slate-500 mb-3">Показва се на страницата след поръчка и в имейла за потвърждение.</p>
          <div className="grid sm:grid-cols-2 gap-4">
            <div><Label>Титуляр</Label><Input value={s.bank_holder || ""} onChange={(e) => set("bank_holder", e.target.value)} data-testid="set-bank-holder" /></div>
            <div><Label>Банка</Label><Input value={s.bank_name || ""} onChange={(e) => set("bank_name", e.target.value)} data-testid="set-bank-name" /></div>
            <div><Label>IBAN</Label><Input className="font-mono" value={s.bank_iban || ""} onChange={(e) => set("bank_iban", e.target.value.toUpperCase())} data-testid="set-bank-iban" /></div>
            <div><Label>BIC / SWIFT</Label><Input className="font-mono" value={s.bank_bic || ""} onChange={(e) => set("bank_bic", e.target.value.toUpperCase())} data-testid="set-bank-bic" /></div>
          </div>
        </div>

        <div className="border-t border-slate-200 pt-5">
          <h2 className="font-bold text-slate-900 mb-3">Кодове за отстъпка</h2>
          <div className="space-y-2" data-testid="discount-codes">
            {(s.discount_codes || []).map((d, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 items-center">
                <Input className="col-span-4 font-mono uppercase" value={d.code}
                  onChange={(e) => { const list = [...s.discount_codes]; list[i] = { ...d, code: e.target.value.toUpperCase() }; set("discount_codes", list); }}
                  data-testid={`discount-code-${i}`} />
                <select className="col-span-3 border border-slate-300 rounded-md px-2 py-2 text-sm" value={d.type}
                  onChange={(e) => { const list = [...s.discount_codes]; list[i] = { ...d, type: e.target.value }; set("discount_codes", list); }}>
                  <option value="percent">%</option>
                  <option value="fixed">EUR</option>
                </select>
                <Input className="col-span-2" type="number" value={d.value}
                  onChange={(e) => { const list = [...s.discount_codes]; list[i] = { ...d, value: Number(e.target.value) }; set("discount_codes", list); }} />
                <Input className="col-span-2" type="number" placeholder="мин. сума" value={d.min_subtotal}
                  onChange={(e) => { const list = [...s.discount_codes]; list[i] = { ...d, min_subtotal: Number(e.target.value) }; set("discount_codes", list); }} />
                <button type="button" className="col-span-1 text-slate-400 hover:text-red-600"
                  onClick={() => set("discount_codes", s.discount_codes.filter((_, x) => x !== i))}>×</button>
              </div>
            ))}
          </div>
          <Button type="button" variant="outline" className="mt-3"
            onClick={() => set("discount_codes", [...(s.discount_codes || []), { code: "NEW10", type: "percent", value: 10, min_subtotal: 0, active: true }])}
            data-testid="add-discount-btn">
            + Нов код
          </Button>
        </div>
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
