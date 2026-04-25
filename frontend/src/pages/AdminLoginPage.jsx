import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { useAuth } from "../context/AuthContext";
import { formatErr } from "../lib/api";

export default function AdminLoginPage() {
  const { user, login, loading } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user?.role === "admin") nav("/admin");
  }, [user, loading, nav]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await login(form.email, form.password);
      if (u.role !== "admin") { toast.error("Профилът няма администраторски достъп"); return; }
      nav("/admin");
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl p-8">
        <Link to="/" className="flex flex-col items-center mb-6">
          <img src="/logo.svg" alt="PurePeptide" className="h-9 w-auto" />
          <p className="text-xs uppercase tracking-widest text-slate-500 mt-2">Admin портал</p>
        </Link>
        <form onSubmit={submit} className="space-y-4">
          <div><Label>Имейл</Label><Input type="email" required value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} data-testid="admin-email" /></div>
          <div><Label>Парола</Label><Input type="password" required value={form.password} onChange={(e) => setForm({...form, password: e.target.value})} data-testid="admin-password" /></div>
          <Button type="submit" disabled={busy} className="w-full bg-coral-600 hover:bg-coral-700" data-testid="admin-login-submit">{busy ? "…" : "Вход"}</Button>
        </form>
        <p className="text-xs text-slate-400 mt-6 text-center">Достъп до тази страница имат само администратори.</p>
      </div>
    </div>
  );
}
