import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "./context/AuthContext";
import { CartProvider } from "./context/CartContext";
import { LocaleProvider } from "./i18n/LocaleContext";
import { LOCALES, DEFAULT_LOCALE } from "./i18n/locales";
import HomePage from "./pages/HomePage";
import CollectionPage from "./pages/CollectionPage";
import ProductPage from "./pages/ProductPage";
import ArticlePage from "./pages/ArticlePage";
import CartPage from "./pages/CartPage";
import CheckoutPage from "./pages/CheckoutPage";
import CheckoutSuccessPage from "./pages/CheckoutSuccessPage";
import AccountPage from "./pages/AccountPage";
import AdminLoginPage from "./pages/AdminLoginPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import AdminProductsPage from "./pages/AdminProductsPage";
import AdminProductEditPage from "./pages/AdminProductEditPage";
import AdminOrdersPage from "./pages/AdminOrdersPage";
import AdminCustomersPage from "./pages/AdminCustomersPage";
import AdminImportPage from "./pages/AdminImportPage";
import AdminSettingsPage from "./pages/AdminSettingsPage";
import AdminDelistedLinksPage from "./pages/AdminDelistedLinksPage";
import AdminLocalesPage from "./pages/AdminLocalesPage";
import AdminPagesPage from "./pages/AdminPagesPage";
import AdminAnalyticsPage from "./pages/AdminAnalyticsPage";
import AdminInventoryPage from "./pages/AdminInventoryPage";
import AdminOrderDetailPage from "./pages/AdminOrderDetailPage";
import StaticPage from "./pages/StaticPage";

const STOREFRONT = [
  { path: "/", el: <HomePage /> },
  { path: "/collections", el: <CollectionPage /> },
  { path: "/collections/:handle", el: <CollectionPage /> },
  { path: "/products/:handle", el: <ProductPage /> },
  { path: "/articles/:handle", el: <ArticlePage /> },
  { path: "/cart", el: <CartPage /> },
  { path: "/checkout", el: <CheckoutPage /> },
  { path: "/checkout/success/:orderId", el: <CheckoutSuccessPage /> },
  { path: "/pages/:slug", el: <StaticPage /> },
  { path: "/account/*", el: <AccountPage /> },
];

const PREFIXES = ["", ...LOCALES.filter((l) => l !== DEFAULT_LOCALE).map((l) => `/${l}`)];

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <CartProvider>
          <BrowserRouter>
            <LocaleProvider>
              <Toaster position="top-right" richColors />
              <Routes>
                {PREFIXES.map((prefix) =>
                  STOREFRONT.map((r) => (
                    <Route key={`${prefix}${r.path}`} path={`${prefix}${r.path}`} element={r.el} />
                  ))
                )}
                <Route path="/admin/login" element={<AdminLoginPage />} />
                <Route path="/admin" element={<AdminDashboardPage />} />
                <Route path="/admin/products" element={<AdminProductsPage />} />
                <Route path="/admin/products/new" element={<AdminProductEditPage />} />
                <Route path="/admin/products/:id" element={<AdminProductEditPage />} />
                <Route path="/admin/orders" element={<AdminOrdersPage />} />
                <Route path="/admin/orders/:id" element={<AdminOrderDetailPage />} />
                <Route path="/admin/analytics" element={<AdminAnalyticsPage />} />
                <Route path="/admin/inventory" element={<AdminInventoryPage />} />
                <Route path="/admin/customers" element={<AdminCustomersPage />} />
                <Route path="/admin/import" element={<AdminImportPage />} />
                <Route path="/admin/settings" element={<AdminSettingsPage />} />
                <Route path="/admin/delisted-links" element={<AdminDelistedLinksPage />} />
                <Route path="/admin/locales" element={<AdminLocalesPage />} />
                <Route path="/admin/pages" element={<AdminPagesPage />} />
              </Routes>
            </LocaleProvider>
          </BrowserRouter>
        </CartProvider>
      </AuthProvider>
    </div>
  );
}

export default App;
