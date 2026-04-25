import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import Layout from "../components/Layout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Badge } from "../components/ui/badge";
import { useAuth } from "../context/AuthContext";
import { api, fmtEUR, formatErr } from "../lib/api";

const STATUS_BG = {
  awaiting_payment: { label: "Очаква плащане", cls: "bg-amber-100 text-amber-800 border-amber-300" },
  paid: { label: "Платена", cls: "bg-coral-100 text-coral-800 border-coral-300" },
  cancelled: { label: "Отказана", cls: "bg-slate-200 text-slate-700 border-slate-300" },
  shipped: { label: "Изпратена", cls: "bg-emerald-100 text-emerald-800 border-emerald-300" },
  fulfilled: { label: "Завършена", cls: "bg-emerald-100 text-emerald-800 border-emerald-300" },
  unfulfilled: { label: "Очаква изпращане", cls: "bg-slate-100 text-slate-700 border-slate-300" },
};

export default function AccountPage() {
  const { user, login, register, logout } = useAuth();
  const [orders, setOrders] = useState([]);
  const [li, setLi] = useState({ email: "", password: "" });
  const [reg, setReg] = useState({ email: "", password: "", name: "", phone: "" });
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();

  useEffect(() => {
    if (user) api.get("/me/orders").then(({ data }) => setOrders(data.orders));
  }, [user]);

  const doLogin = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await login(li.email, li.password);
      toast.success("Добре дошли");
      if (u.role === "admin") nav("/admin");
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };
  const doRegister = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await register(reg);
      toast.success("Регистрацията е успешна");
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  if (!user) {
    return (
      <Layout>
        <div className="max-w-md mx-auto px-4 py-16">
          <h1 className="font-display text-3xl font-extrabold text-slate-900 mb-8 text-center">Моят профил</h1>
          <Tabs defaultValue="login">
            <TabsList className="grid grid-cols-2 w-full">
              <TabsTrigger value="login" data-testid="tab-login">Вход</TabsTrigger>
              <TabsTrigger value="register" data-testid="tab-register">Регистрация</TabsTrigger>
            </TabsList>
            <TabsContent value="login">
              <form onSubmit={doLogin} className="bg-white border border-slate-200 rounded-xl p-6 space-y-4 mt-4">
                <div><Label>Имейл</Label><Input type="email" required value={li.email} onChange={(e) => setLi({...li, email: e.target.value})} data-testid="login-email" /></div>
                <div><Label>Парола</Label><Input type="password" required value={li.password} onChange={(e) => setLi({...li, password: e.target.value})} data-testid="login-password" /></div>
                <Button type="submit" disabled={busy} className="w-full bg-coral-600 hover:bg-coral-700" data-testid="login-submit">{busy ? "…" : "Вход"}</Button>
              </form>
            </TabsContent>
            <TabsContent value="register">
              <form onSubmit={doRegister} className="bg-white border border-slate-200 rounded-xl p-6 space-y-4 mt-4">
                <div><Label>Имена</Label><Input value={reg.name} onChange={(e) => setReg({...reg, name: e.target.value})} data-testid="register-name" /></div>
                <div><Label>Имейл</Label><Input type="email" required value={reg.email} onChange={(e) => setReg({...reg, email: e.target.value})} data-testid="register-email" /></div>
                <div><Label>Телефон</Label><Input value={reg.phone} onChange={(e) => setReg({...reg, phone: e.target.value})} data-testid="register-phone" /></div>
                <div><Label>Парола</Label><Input type="password" required minLength={6} value={reg.password} onChange={(e) => setReg({...reg, password: e.target.value})} data-testid="register-password" /></div>
                <Button type="submit" disabled={busy} className="w-full bg-coral-600 hover:bg-coral-700" data-testid="register-submit">{busy ? "…" : "Създай профил"}</Button>
              </form>
            </TabsContent>
          </Tabs>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-5xl mx-auto px-4 py-12">
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="font-display text-4xl font-extrabold text-slate-900">Здравейте, {user.name || user.email}</h1>
            <p className="text-slate-500 mt-2">{user.email}</p>
          </div>
          <Button variant="outline" onClick={logout} data-testid="logout-btn">Изход</Button>
        </div>

        <h2 className="font-display text-2xl font-bold text-slate-900 mb-4">Моите поръчки</h2>
        {orders.length === 0 ? (
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-10 text-center text-slate-500">
            Все още нямате поръчки. <Link to="/collections/all-peptides" className="text-coral-600 font-medium">Към каталога →</Link>
          </div>
        ) : (
          <div className="space-y-3">
            {orders.map((o) => {
              const ps = STATUS_BG[o.payment_status] || { label: o.payment_status, cls: "bg-slate-100 text-slate-700 border-slate-300" };
              const fs = STATUS_BG[o.fulfillment_status] || { label: o.fulfillment_status, cls: "bg-slate-100 text-slate-700 border-slate-300" };
              return (
                <div key={o.id} className="bg-white border border-slate-200 rounded-xl p-5 flex flex-wrap gap-4 items-center" data-testid={`order-${o.order_number}`}>
                  <div>
                    <p className="font-mono font-semibold text-slate-900">{o.order_number}</p>
                    <p className="text-xs text-slate-500">{new Date(o.created_at).toLocaleDateString("bg-BG")}</p>
                  </div>
                  <div className="flex gap-2">
                    <Badge className={`${ps.cls} border`}>{ps.label}</Badge>
                    <Badge className={`${fs.cls} border`}>{fs.label}</Badge>
                  </div>
                  <div className="ml-auto text-right">
                    <p className="font-display font-bold text-slate-900">{fmtEUR(o.total_eur)}</p>
                    <p className="text-xs text-slate-500">{o.items.length} артикула</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Layout>
  );
}
