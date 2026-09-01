import { useState } from "react";
import { toast } from "sonner";
import { api, formatErr } from "../lib/api";

const empty = { name: "", email: "", phone: "", message: "" };

export const ContactForm = () => {
  const [form, setForm] = useState(empty);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  const set = (k) => (e) => setForm((c) => ({ ...c, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.email.includes("@") || !form.message.trim()) {
      toast.error("Моля попълнете име, валиден имейл и коментар");
      return;
    }
    setBusy(true);
    try {
      await api.post("/contact", form);
      setForm(empty);
      setSent(true);
      toast.success("Благодарим! Ще отговорим в рамките на 24 часа.");
    } catch (err) { toast.error(formatErr(err)); } finally { setBusy(false); }
  };

  return (
    <form onSubmit={submit} className="mt-8 space-y-3 max-w-xl" data-testid="contact-form">
      <input value={form.name} onChange={set("name")} placeholder="Име"
        className="w-full border border-slate-300 rounded-md px-4 py-3.5 text-base outline-none focus:border-coral-500"
        data-testid="contact-name" />
      <input value={form.email} onChange={set("email")} type="email" placeholder="Имейл адрес"
        className="w-full border border-slate-300 rounded-md px-4 py-3.5 text-base outline-none focus:border-coral-500"
        data-testid="contact-email" />
      <input value={form.phone} onChange={set("phone")} placeholder="Телефон"
        className="w-full border border-slate-300 rounded-md px-4 py-3.5 text-base outline-none focus:border-coral-500"
        data-testid="contact-phone" />
      <textarea value={form.message} onChange={set("message")} placeholder="Коментар" rows={7}
        className="w-full border border-slate-300 rounded-md px-4 py-3.5 text-base outline-none focus:border-coral-500"
        data-testid="contact-message" />
      <button type="submit" disabled={busy}
        className="w-full bg-coral-600 hover:bg-coral-700 text-white font-semibold py-4 rounded-md text-base disabled:opacity-60"
        data-testid="contact-submit">
        {busy ? "Изпращане…" : "Изпрати"}
      </button>
      {sent && (
        <p className="text-sm text-emerald-700" data-testid="contact-success">
          Съобщението е изпратено. Ще получите отговор на посочения имейл.
        </p>
      )}
    </form>
  );
};
