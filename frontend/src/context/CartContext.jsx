import { createContext, useContext, useEffect, useState, useMemo } from "react";

const CartCtx = createContext(null);
const KEY = "pp_cart_v1";

export const CartProvider = ({ children }) => {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY) || "[]");
      if (Array.isArray(saved)) setItems(saved);
    } catch {}
  }, []);

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(items));
  }, [items]);

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
  const clear = () => setItems([]);

  const subtotal = useMemo(() => items.reduce((s, x) => s + x.price_eur * x.quantity, 0), [items]);
  const count = useMemo(() => items.reduce((s, x) => s + x.quantity, 0), [items]);

  return (
    <CartCtx.Provider value={{ items, add, remove, updateQty, clear, subtotal, count, open, setOpen }}>
      {children}
    </CartCtx.Provider>
  );
};

export const useCart = () => useContext(CartCtx);
