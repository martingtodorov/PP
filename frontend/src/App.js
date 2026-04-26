import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "./context/AuthContext";
import { CartProvider } from "./context/CartContext";
import HomePage from "./pages/HomePage";
import CollectionPage from "./pages/CollectionPage";
import ProductPage from "./pages/ProductPage";
import CartPage from "./pages/CartPage";
import CheckoutPage from "./pages/CheckoutPage";
import CheckoutSuccessPage from "./pages/CheckoutSuccessPage";
import AccountPage from "./pages/AccountPage";
import AdminLoginPage from "./pages/AdminLoginPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import AdminProductsPage from "./pages/AdminProductsPage";
import AdminOrdersPage from "./pages/AdminOrdersPage";
import AdminCustomersPage from "./pages/AdminCustomersPage";
import AdminImportPage from "./pages/AdminImportPage";
import AdminSettingsPage from "./pages/AdminSettingsPage";
import StaticPage from "./pages/StaticPage";

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <CartProvider>
          <BrowserRouter>
            <Toaster position="top-right" richColors />
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/collections/:handle" element={<CollectionPage />} />
              <Route path="/collections" element={<CollectionPage />} />
              <Route path="/products/:handle" element={<ProductPage />} />
              <Route path="/cart" element={<CartPage />} />
              <Route path="/checkout" element={<CheckoutPage />} />
              <Route path="/checkout/success/:orderId" element={<CheckoutSuccessPage />} />
              <Route path="/pages/:slug" element={<StaticPage />} />
              <Route path="/account/*" element={<AccountPage />} />
              <Route path="/admin/login" element={<AdminLoginPage />} />
              <Route path="/admin" element={<AdminDashboardPage />} />
              <Route path="/admin/products" element={<AdminProductsPage />} />
              <Route path="/admin/orders" element={<AdminOrdersPage />} />
              <Route path="/admin/customers" element={<AdminCustomersPage />} />
              <Route path="/admin/import" element={<AdminImportPage />} />
              <Route path="/admin/settings" element={<AdminSettingsPage />} />
            </Routes>
          </BrowserRouter>
        </CartProvider>
      </AuthProvider>
    </div>
  );
}

export default App;
