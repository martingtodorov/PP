import { createContext, useContext, useEffect, useState, useMemo } from "react";
import { api } from "../lib/api";

const CartCtx = createContext(null);
const KEY = "pp_cart_v1";
const META_KEY = "pp_cart_meta_v1";

export const CartProvider = ({ children }) => {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [note, setNote] = useState("");
  const [discount, setDiscount] = useState(null); // { code, discount_eur }

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY) || "[]");
      if (Array.isArray(saved)) setItems(saved);
      const meta = JSON.parse(localStorage.getItem(META_KEY) || "{}");
      if (meta.note) setNote(meta.note);
      if (meta.discount) setDiscount(meta.discount);
    } catch {}
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem(KEY, JSON.stringify(items));
  }, [items, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem(META_KEY, JSON.stringify({ note, discount }));
  }, [note, discount, hydrated]);

  const add = (product, variant, quantity = 1) => {
    setItems((cur) => {
      const idx = cur.findIndex((x) => x.product_id === product.id && x.variant_sku === variant.sku);
      if (idx >= 0) {
        const next = [...cur];
        next[idx] = { ...next[idx], quantity: next[idx].quantity + quantity };
        return next;
      }
      return [
        ...cur,
        {
          product_id: product.id,
          product_handle: product.handle,
          title: product.title,
          image: product.image,
          variant_sku: variant.sku,
          variant_name: variant.name,
          price_eur: variant.price_eur,
          quantity,
        },
      ];
    });
    setOpen(true);
  };

  const remove = (sku) => setItems((cur) => cur.filter((x) => x.variant_sku !== sku));
  const updateQty = (sku, qty) =>
    setItems((cur) => cur.map((x) => (x.variant_sku === sku ? { ...x, quantity: Math.max(1, qty) } : x)));
  const clear = () => { setItems([]); setNote(""); setDiscount(null); };

  const subtotal = useMemo(() => items.reduce((s, x) => s + x.price_eur * x.quantity, 0), [items]);
  const count = useMemo(() => items.reduce((s, x) => s + x.quantity, 0), [items]);

  const applyDiscount = async (code) => {
    const { data } = await api.post("/discount/validate", { code, subtotal_eur: subtotal });
    setDiscount(data);
    return data;
  };
  const removeDiscount = () => setDiscount(null);

  const discountAmount = useMemo(() => {
    if (!discount) return 0;
    if (discount.type === "percent") return Math.min(subtotal * discount.value / 100, subtotal);
    return Math.min(discount.discount_eur || 0, subtotal);
  }, [discount, subtotal]);

  const total = Math.max(subtotal - discountAmount, 0);

  return (
    <CartCtx.Provider
      value={{
        items, add, remove, updateQty, clear, subtotal, count, open, setOpen,
        note, setNote, discount, applyDiscount, removeDiscount, discountAmount, total,
      }}
    >
      {children}
    </CartCtx.Provider>
  );
};

export const useCart = () => useContext(CartCtx);
