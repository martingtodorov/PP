import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { X, Minus, Plus, Trash2, Loader2, Check, Search } from "lucide-react";
import { toast } from "sonner";
import { api, fmtEUR, fmtBGN, showsBGN, img, formatErr } from "../lib/api";
import { loadSaved, saveCheckout, pfBank, pfCountries, pfGeo, pfConfig, pfPickups } from "../lib/checkoutPrefetch";
import { siteMedia } from "../lib/media";
import { useCart } from "../context/CartContext";
import { useLocaleCtx } from "../i18n/LocaleContext";

const BG_PROVIDER = {
  econt: "Еконт", boxnow: "BoxNow", pigeon: "Pigeon Express", speedy: "Спиди",
  gls: "GLS", fancourier: "FAN Courier", speedex: "Speedex", acs: "ACS",
  postasi: "Pošta Slovenije", brt: "BRT",
};
const DEST_WORD = { office: "до офис", locker: "до кутия", address: "до адрес" };
const track = (event_name, event_data = {}) => {
  api.post("/nextcart/event", { event_name, event_data }).catch(() => {});
};

const methodLabel = (m) => {
  const p = BG_PROVIDER[m.provider_key] || m.provider_name;
  if (m.destination_type === "locker") return `До автомат на ${p}`;
  if (m.destination_type === "address") return `До адрес с ${p}`;
  return `До офис на ${p}`;
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i;

/** Strip punctuation (№, ., -, …) so "Витоша 150" matches "бул. Витоша №150". */
const norm = (v) => (v || "").toString().toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
const tokensOf = (v) => norm(v).split(" ").filter(Boolean);

/** Relevance of a record against the typed tokens — exact city hits always beat name/address hits. */
const matchScore = (fields, tokens) => {
  let total = 0;
  for (const tok of tokens) {
    let best = 0;
    for (const f of fields) {
      const t = norm(f.text);
      if (!t) continue;
      const words = t.split(" ");
      let s = 0;
      if (t === tok) s = 100;
      else if (t.startsWith(tok)) s = 82;
      else if (words.includes(tok)) s = 70;
      else if (words.some((w) => w.startsWith(tok))) s = 55;
      else if (t.includes(tok)) s = 22;
      best = Math.max(best, s * f.weight);
    }
    total += best;
  }
  return total;
};

/** "София — София Иван Вазов" -> "София Иван Вазов" (never repeat the city). */
const dedupeCity = (city, text) => {
  const c = norm(city);
  const t = norm(text);
  if (!c) return (text || "").trim();
  if (!t) return city;
  if (t === c || t.startsWith(`${c} `)) return (text || "").trim();
  return `${city} — ${text}`;
};

/** Checkout details are remembered for 90 days (see lib/checkoutPrefetch.js). */

/** Searchable dropdown over the full pickup list (Econt offices / BoxNow lockers / GLS points). */
const PickupSelect = ({ options, value, onChange, placeholder, loading, geoCity }) => {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const box = useRef(null);

  useEffect(() => {
    const away = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, []);

  const hits = useMemo(() => {
    const here = norm(geoCity);
    const tokens = tokensOf(q);
    if (!tokens.length) {
      // no query yet — offices in the visitor's own city (from IP) come first
      return [...options]
        .sort((a, b) => (norm(b.city) === here ? 1 : 0) - (norm(a.city) === here ? 1 : 0))
        .slice(0, 80);
    }
    return options
      .filter((o) => {
        const hay = norm(`${o.city} ${o.name} ${o.address} ${o.postal_code}`);
        return tokens.every((tok) => hay.includes(tok));
      })
      .map((o) => ({
        o,
        s: matchScore(
          [{ text: o.city, weight: 1 }, { text: o.name, weight: 0.6 },
           { text: o.address, weight: 0.5 }, { text: o.postal_code, weight: 0.45 }],
          tokens,
        ) + (here && norm(o.city) === here ? 12 : 0),
      }))
      .sort((a, b) => b.s - a.s)
      .slice(0, 80)
      .map((x) => x.o);
  }, [q, options, geoCity]);

  return (
    <div className="nc2-pickup" ref={box}>
      <div className="nc2-combo" onClick={() => setOpen(true)}>
        <Search className="h-4 w-4 text-slate-400 shrink-0" />
        <input className="nc2-combo-inp" value={open ? q : value ? dedupeCity(value.city, value.name) : q}
          placeholder={loading ? "Зареждане…" : placeholder}
          onFocus={() => setOpen(true)}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          data-testid="pc-pickup-search" />
        {value && !open && <Check className="h-4 w-4 text-coral-600 shrink-0" />}
      </div>
      {open && (
        <div className="nc2-dropdown" data-testid="pc-pickup-results">
          {hits.length === 0 && <p className="nc2-muted px-3 py-2">Няма резултати</p>}
          {hits.map((o) => (
            <button type="button" key={o.id} className="nc2-opt"
              onClick={() => { onChange(o); setOpen(false); setQ(""); track("checkout_pickup_selected", { id: o.id }); }}>
              <span className="nc2-opt-1">{dedupeCity(o.city, o.name)}</span>
              <span className="nc2-opt-2">{o.postal_code} · {o.address}</span>
            </button>
          ))}
          {options.length > hits.length && <p className="nc2-muted px-3 py-2">Покажи още — уточни търсенето</p>}
        </div>
      )}
    </div>
  );
};

/** Predictive input backed by the courier address database (city / street & quarter).
 *  Supports fragmented queries in the street field: "София Иван Вазов" resolves the city first. */
const AddressSuggest = ({ mode, value, onPick, onChangeText, placeholder, placeId, testId, country, providerKey, geoCity }) => {
  const [q, setQ] = useState(value || "");
  const [hits, setHits] = useState([]);
  const [open, setOpen] = useState(false);
  const timer = useRef(null);
  const seq = useRef(0);

  useEffect(() => { setQ(value || ""); }, [value]);

  const fetchSug = async (m, text, pid) => {
    const { data } = await api.get("/nextcart/address-suggestions", {
      params: { mode: m, q: text, provider_key: providerKey || "econt", country, place_id: pid || undefined },
    });
    return data.suggestions || [];
  };

  const rank = (list, text, fields) => {
    const tokens = tokensOf(text);
    const here = norm(geoCity);
    return [...list]
      .map((s) => ({ s, v: matchScore(fields(s), tokens) + (here && norm(s.city) === here ? 12 : 0) }))
      .sort((a, b) => b.v - a.v)
      .map((x) => x.s);
  };

  const cityFields = (s) => [{ text: s.city, weight: 1 }, { text: s.postal_code, weight: 0.45 }];
  const streetFields = (s) => [{ text: s.address1, weight: 1 }, { text: s.city, weight: 0.4 }];

  const run = async (text) => {
    const mine = ++seq.current;
    const clean = text.trim();
    const words = clean.split(/\s+/).filter(Boolean);

    if (mode === "city") {
      let list = await fetchSug("city", clean);
      for (let n = words.length - 1; n >= 1 && list.length === 0; n -= 1) {
        list = await fetchSug("city", words.slice(0, n).join(" "));
      }
      if (mine === seq.current) setHits(rank(list, clean, cityFields).slice(0, 40));
      return;
    }

    let pid = placeId;
    let rest = clean;
    let cityHit = null;
    if (!pid) {
      for (let n = Math.min(3, words.length); n >= 1 && !pid; n -= 1) {
        const cq = words.slice(0, n).join(" ");
        if (cq.length < 2) continue;
        const cities = rank(await fetchSug("city", cq), cq, cityFields);
        if (cities.length) {
          pid = cities[0].place_id;
          cityHit = cities[0];
          rest = words.slice(n).join(" ");
        }
      }
    }
    if (!pid || rest.trim().length < 2) {
      if (mine === seq.current) setHits([]);
      return;
    }
    const streets = rank(await fetchSug("street", rest.trim(), pid), rest, streetFields);
    if (mine === seq.current) {
      setHits(streets.slice(0, 40).map((s) => ({
        ...s,
        city: s.city || cityHit?.city || "",
        postal_code: s.postal_code || cityHit?.postal_code || "",
        place_id: s.place_id || pid,
      })));
    }
  };

  const search = (text) => {
    setQ(text);
    setOpen(true);
    if (onChangeText) onChangeText(text);
    clearTimeout(timer.current);
    if (text.trim().length < 2) { setHits([]); return; }
    timer.current = setTimeout(() => { run(text).catch(() => setHits([])); }, 260);
  };

  return (
    <div className="nc2-pickup">
      <input className="nc2-inp" value={q} placeholder={placeholder}
        onChange={(e) => search(e.target.value)} onFocus={() => setOpen(true)} data-testid={testId} />
      {open && hits.length > 0 && (
        <div className="nc2-dropdown" data-testid={`${testId}-results`}>
          {hits.map((s, i) => (
            <button type="button" key={`${s.place_id || s.address1}-${i}`} className="nc2-opt"
              onClick={() => { onPick(s); setOpen(false); setQ(mode === "city" ? s.city : s.address1); }}>
              <span className="nc2-opt-1">
                {mode === "city" ? `${s.postal_code} ${s.city}`.trim() : s.address1}
              </span>
              {mode === "street" && <span className="nc2-opt-2">{s.city} · {s.postal_code}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default function PreCheckoutModal({ open, onClose, termsAccepted = false }) {
  const nav = useNavigate();
  const { lp, locale } = useLocaleCtx();
  const { items, updateQty, remove, subtotal, discount, discountAmount, applyDiscount, clear } = useCart();
  const [cfg, setCfg] = useState(null);
  const [err, setErr] = useState("");
  const [provider, setProvider] = useState("");
  const [methodKey, setMethodKey] = useState("");
  const saved = useRef(loadSaved());
  const [contact, setContact] = useState(saved.current?.contact
    || { name: "", email: "", phone: "", dial: "359", country: "BG" });
  const [pickups, setPickups] = useState([]);
  const [loadingPickups, setLoadingPickups] = useState(false);
  const [pickup, setPickup] = useState(saved.current?.pickup || null);
  const [addr, setAddr] = useState(saved.current?.addr
    || { city: "", postal_code: "", place_id: null, street: "", number: "" });
  const [payment, setPayment] = useState(saved.current?.payment || "cod");
  const [geo, setGeo] = useState(null);
  const [countries, setCountries] = useState([]);
  const [bank, setBank] = useState(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  // lock the page behind the overlay, the overlay itself scrolls
  useEffect(() => {
    if (!open) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setErr("");
    pfBank().then(setBank).catch(() => {});
    pfCountries().then((d) => setCountries(d.countries || [])).catch(() => {});
    pfGeo().then(setGeo).catch(() => {});
    track("checkout_opened");
  }, [open]);

  // visitor's country from IP — only if we actually ship there and nothing was remembered
  useEffect(() => {
    if (!countries.length || !geo?.country || saved.current?.contact?.country) return;
    if (countries.some((c) => c.iso2 === geo.country)) {
      setContact((c) => (c.country === geo.country ? c : { ...c, country: geo.country }));
    }
  }, [countries, geo]);

  // couriers and prices depend on the destination country
  useEffect(() => {
    if (!open) return;
    setCfg(null);
    pfConfig(contact.country)
      .then((data) => {
        setCfg(data);
        const list = data.delivery_methods || [];
        const remembered = list.find((m) => m.key === saved.current?.methodKey);
        const def = remembered || list.find((m) => m.is_default) || list[0];
        setProvider(def ? def.provider_key : "");
        setMethodKey(def ? def.key : "");
      })
      .catch((e) => setErr(formatErr(e)));
  }, [open, contact.country]);

  const methods = useMemo(
    () => (cfg?.delivery_methods || []).filter((m) => m.provider_key === provider),
    [cfg, provider],
  );
  const method = useMemo(() => methods.find((m) => m.key === methodKey) || methods[0], [methods, methodKey]);
  const needsPickup = method && method.destination_type !== "address";
  const needsAddress = method && method.destination_type === "address";

  /** "до офис" / "до кутия" / "до адрес" under each courier logo. */
  const providerSub = (key) => {
    const seen = [];
    (cfg?.delivery_methods || []).forEach((m) => {
      if (m.provider_key === key && DEST_WORD[m.destination_type] && !seen.includes(m.destination_type)) {
        seen.push(m.destination_type);
      }
    });
    return seen.map((d) => DEST_WORD[d]).join(" / ");
  };

  // cash on delivery is the default everywhere we ship (unless the visitor changed it before)
  const prevCountry = useRef(contact.country);
  useEffect(() => {
    if (prevCountry.current === contact.country) return;
    prevCountry.current = contact.country;
    setPayment("cod");
  }, [contact.country]);

  // country -> dial code (until the customer picks a different prefix himself)
  const dialTouched = useRef(Boolean(saved.current?.dialTouched));
  useEffect(() => {
    if (dialTouched.current) return;
    const own = countries.find((c) => c.iso2 === contact.country);
    const t = own?.dial ? own : (cfg?.precheckout_phone_territories || []).find((x) => x.iso2 === contact.country);
    if (t?.dial) setContact((c) => (c.dial === t.dial ? c : { ...c, dial: t.dial }));
  }, [cfg, countries, contact.country]);

  /** Every prefix the courier platform knows, so a Bulgarian phone can ship to Greece. */
  const dialOptions = useMemo(() => {
    const src = (cfg?.precheckout_phone_territories || []).length
      ? cfg.precheckout_phone_territories : countries;
    const seen = new Set();
    const list = [];
    (src || []).forEach((x) => {
      const key = `${x.iso2}-${x.dial}`;
      if (!x.dial || seen.has(key)) return;
      seen.add(key);
      list.push({ iso2: x.iso2, dial: String(x.dial), name: x.name || x.iso2 });
    });
    if (!list.some((x) => x.dial === contact.dial)) {
      list.unshift({ iso2: contact.country, dial: contact.dial, name: contact.country });
    }
    return list;
  }, [cfg, countries, contact.dial, contact.country]);

  // full pickup list for the chosen method
  useEffect(() => {
    if (!needsPickup || !method) { setPickups([]); return; }
    setLoadingPickups(true);
    pfPickups(method.provider_key, method.destination_type, contact.country)
      .then((data) => {
        const list = data.pickups || [];
        setPickups(list);
        setPickup((cur) => {
          if (cur && list.some((o) => String(o.id) === String(cur.id))) return cur;
          const remembered = saved.current?.pickup;
          if (remembered && saved.current?.methodKey === method.key) {
            return list.find((o) => String(o.id) === String(remembered.id)) || null;
          }
          return null;
        });
      })
      .catch(() => setPickups([]))
      .finally(() => setLoadingPickups(false));
  }, [method, needsPickup, contact.country]);

  // IP city pre-fills the address form (only on an exact city match, once)
  const prefilled = useRef(false);
  useEffect(() => {
    if (!needsAddress || !geo?.city || addr.city || prefilled.current) return;
    if (geo.country && geo.country !== contact.country) return;
    prefilled.current = true;
    api.get("/nextcart/address-suggestions", {
      params: { mode: "city", q: geo.city, provider_key: provider || "econt", country: contact.country },
    })
      .then(({ data }) => {
        const exact = (data.suggestions || []).find((s) => norm(s.city) === norm(geo.city));
        if (exact) setAddr((a) => (a.city ? a : { ...a, city: exact.city, postal_code: exact.postal_code, place_id: exact.place_id }));
      })
      .catch(() => {});
  }, [needsAddress, geo, provider, contact.country, addr.city]);

  const shipping = method?.price_amount || 0;
  const total = Math.max(subtotal - discountAmount, 0) + shipping;
  const nameWords = contact.name.trim().split(/\s+/).filter((w) => w.length >= 2);
  const ready = nameWords.length >= 2 && EMAIL_RE.test(contact.email)
    && contact.phone.replace(/\D/g, "").length >= 6 && method && termsAccepted
    && (needsPickup ? !!pickup : addr.city && addr.street);

  // remember everything for 90 days
  useEffect(() => {
    if (!open || !cfg) return;
    saveCheckout({ contact, methodKey: method?.key || methodKey, provider, pickup, addr, payment,
                   dialTouched: dialTouched.current });
  }, [open, cfg, contact, method, methodKey, provider, pickup, addr, payment]);

  // abandoned cart capture — as soon as we have a usable email
  useEffect(() => {
    if (!open || !items.length || !EMAIL_RE.test(contact.email)) return undefined;
    const id = setTimeout(() => {
      api.post("/cart/track", {
        email: contact.email,
        customer_name: contact.name,
        phone: contact.phone ? `+${contact.dial}${contact.phone.replace(/\D/g, "").replace(/^0+/, "")}` : "",
        locale,
        items: items.map((it) => ({
          product_id: it.product_id, variant_sku: it.variant_sku, title: it.title,
          variant_name: it.variant_name, image: it.image, price_eur: it.price_eur, quantity: it.quantity,
        })),
      }).catch(() => {});
    }, 1500);
    return () => clearTimeout(id);
  }, [open, items, contact.email, contact.name, contact.phone, contact.dial, locale]);

  const applyCode = async () => {
    try { await applyDiscount(code); toast.success("Кодът е приложен"); }
    catch (e) { toast.error(formatErr(e)); }
  };

  const placeOrder = async () => {
    setBusy(true);
    try {
      const phone = `+${contact.dial}${contact.phone.replace(/\D/g, "").replace(/^0+/, "")}`;
      const fullName = contact.name.trim().replace(/\s+/g, " ");
      const { data } = await api.post("/checkout", {
        items: items.map((it) => ({ product_id: it.product_id, variant_sku: it.variant_sku, quantity: it.quantity })),
        shipping: {
          full_name: fullName,
          phone,
          email: contact.email,
          line1: pickup ? `${pickup.name}${pickup.address ? `, ${pickup.address}` : ""}` : `${addr.street} ${addr.number}`.trim(),
          city: pickup ? pickup.city : addr.city,
          postal_code: (pickup ? pickup.postal_code : addr.postal_code) || "0000",
          country: contact.country,
        },
        customer_email: contact.email,
        customer_name: fullName,
        customer_phone: phone,
        shipping_method: method.key,
        payment_method: payment,
        delivery: {
          provider_key: method.provider_key,
          provider_name: BG_PROVIDER[method.provider_key] || method.provider_name,
          method_key: method.key,
          destination_type: method.destination_type,
          label: methodLabel(method),
          price_amount: shipping,
          currency: method.currency || "EUR",
          office: pickup ? { id: pickup.id, name: pickup.name, address: pickup.address, city: pickup.city, postal_code: pickup.postal_code } : null,
          address: needsAddress ? { ...addr } : null,
        },
        discount_code: discount?.code || "",
        terms_accepted: termsAccepted,
        locale,
      });
      track("checkout_completed", { order: data.order?.order_number, total });
      clear();
      onClose();
      nav(lp(`/checkout/success/${data.order.id}`));
    } catch (e) {
      toast.error(formatErr(e));
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="nc2-backdrop" role="dialog" aria-modal="true" data-testid="precheckout-modal">
      <div className="nc2-dialog">
        <div className="nc2-hd">
          <img src={siteMedia("logo", "/logo-header.png")} alt="PurePeptide" className="nc2-logo" />
          <span className="nc2-hd-title">Бърза поръчка</span>
          <button type="button" className="nc2-x" aria-label="Затвори" onClick={onClose} data-testid="precheckout-close">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="nc2-body">
          {err && <p className="nc2-err" data-testid="precheckout-error">{err}</p>}
          {!cfg && !err && <p className="nc2-muted"><Loader2 className="h-4 w-4 animate-spin inline mr-2" />Зареждане…</p>}

          {cfg && (
            <div className="nc2-grid">
              <div className="nc2-left">
                <h2 className="nc2-sec-title">Вашите данни</h2>
                <input className="nc2-inp" placeholder="Име и фамилия" autoComplete="name" value={contact.name}
                  onChange={(e) => setContact({ ...contact, name: e.target.value })}
                  onBlur={(e) => setContact((c) => ({ ...c, name: e.target.value }))}
                  data-testid="pc-name" />
                <input className="nc2-inp" type="email" placeholder="Имейл" autoComplete="email" value={contact.email}
                  onChange={(e) => setContact({ ...contact, email: e.target.value })}
                  onBlur={(e) => setContact((c) => ({ ...c, email: e.target.value }))}
                  data-testid="pc-email" />
                <div className="nc2-row2">
                  <select className="nc2-inp" value={contact.country} aria-label="Държава"
                    onChange={(e) => setContact({ ...contact, country: e.target.value })} data-testid="pc-country">
                    {(countries.length ? countries : [{ iso2: contact.country, name: contact.country }]).map((tt) => (
                      <option key={tt.iso2} value={tt.iso2}>{tt.name || tt.iso2}</option>
                    ))}
                  </select>
                  <div className="nc2-phone">
                    <select className="nc2-dial-select" value={contact.dial} aria-label="Код на страната"
                      onChange={(e) => { dialTouched.current = true; setContact({ ...contact, dial: e.target.value }); }}
                      data-testid="pc-dial">
                      {dialOptions.map((d) => (
                        <option key={`${d.iso2}-${d.dial}`} value={d.dial}>+{d.dial} {d.iso2}</option>
                      ))}
                    </select>
                    <input className="nc2-inp" placeholder="Телефон" autoComplete="tel" value={contact.phone}
                      onChange={(e) => setContact({ ...contact, phone: e.target.value })}
                      onBlur={(e) => setContact((c) => ({ ...c, phone: e.target.value }))}
                      data-testid="pc-phone" />
                  </div>
                </div>

                <h2 className="nc2-sec-title mt-6">Доставка</h2>
                <div className="nc2-couriers" data-testid="pc-couriers">
                  {(cfg.delivery_providers || []).map((p) => (
                    <button key={p.key} type="button"
                      className={`nc2-courier${provider === p.key ? " nc2-courier--on" : ""}`}
                      onClick={() => {
                        setProvider(p.key);
                        setPickup(null);
                        const m = (cfg.delivery_methods || []).find((x) => x.provider_key === p.key);
                        setMethodKey(m ? m.key : "");
                        track("checkout_courier_selected", { provider: p.key });
                      }}
                      data-testid={`pc-courier-${p.key}`}>
                      <img src={p.logo_url} alt={BG_PROVIDER[p.key] || p.name} />
                      <span className="nc2-courier-sub">{providerSub(p.key)}</span>
                    </button>
                  ))}
                </div>
                {!(cfg.delivery_providers || []).length && (
                  <p className="nc2-err" data-testid="pc-no-delivery">
                    {cfg.delivery_unavailable_message || "За тази държава все още не предлагаме доставка."}
                  </p>
                )}

                <div className="nc2-methods">
                  {methods.map((m) => (
                    <label key={m.key} className={`nc2-method${method?.key === m.key ? " nc2-method--on" : ""}`}
                      data-testid={`pc-method-${m.key}`}>
                      <input type="radio" name="pc-method" checked={method?.key === m.key}
                        onChange={() => { setMethodKey(m.key); setPickup(null); }} />
                      <span className="nc2-method-label">{methodLabel(m)}</span>
                      <span className="nc2-method-price">{fmtEUR(m.price_amount)}</span>
                    </label>
                  ))}
                </div>

                {needsPickup && (
                  <PickupSelect options={pickups} value={pickup} onChange={setPickup} loading={loadingPickups}
                    geoCity={geo?.city}
                    placeholder={`${method.destination_type === "locker" ? "Избери автомат" : "Избери офис"}`
                      + ` (${pickups.length})`
                      + (geo?.city ? ` — най-близки до ${geo.city}` : "")} />
                )}

                {needsAddress && (
                  <div className="space-y-0">
                    <AddressSuggest mode="city" testId="pc-city" placeholder="Град"
                      value={addr.city} country={contact.country} providerKey={provider} geoCity={geo?.city}
                      onChangeText={(t) => setAddr((a) => ({ ...a, city: t, place_id: null }))}
                      onPick={(s) => setAddr({ ...addr, city: s.city, postal_code: s.postal_code, place_id: s.place_id, street: "" })} />
                    <AddressSuggest mode="street" testId="pc-street" placeId={addr.place_id}
                      placeholder="Улица / квартал"
                      value={addr.street} country={contact.country} providerKey={provider} geoCity={geo?.city}
                      onPick={(s) => setAddr({
                        ...addr,
                        city: addr.city || s.city || "",
                        place_id: addr.place_id || s.place_id || null,
                        street: s.address1,
                        postal_code: s.postal_code || addr.postal_code,
                      })} />
                    <div className="nc2-row2">
                      <input className="nc2-inp" placeholder="№ / бл. / вх. / ап." value={addr.number}
                        onChange={(e) => setAddr({ ...addr, number: e.target.value })} data-testid="pc-number" />
                      <input className="nc2-inp" placeholder="Пощенски код" value={addr.postal_code}
                        onChange={(e) => setAddr({ ...addr, postal_code: e.target.value })} data-testid="pc-postal" />
                    </div>
                  </div>
                )}

                <h2 className="nc2-sec-title mt-6">Плащане</h2>
                <div className="nc2-methods">
                  {(cfg.payment_methods || [{ key: "cod", label: "Наложен платеж при получаване" }, { key: "bank_transfer", label: "Банков превод" }]).map((pm) => (
                    <label key={pm.key} className={`nc2-method${payment === pm.key ? " nc2-method--on" : ""}`} data-testid={`pc-payment-${pm.key}`}>
                      <input type="radio" name="pc-payment" checked={payment === pm.key} onChange={() => setPayment(pm.key)} />
                      <span className="nc2-method-label">{pm.label}</span>
                    </label>
                  ))}
                </div>
                {payment === "bank_transfer" && bank && (
                  <div className="nc2-bank" data-testid="pc-bank-details">
                    <p className="nc2-bank-row"><span>Банка</span><strong>{bank.name}</strong></p>
                    <p className="nc2-bank-row"><span>Получател</span><strong>{bank.holder}</strong></p>
                    <p className="nc2-bank-row"><span>IBAN</span><strong>{bank.iban}</strong></p>
                    <p className="nc2-bank-row"><span>BIC</span><strong>{bank.bic}</strong></p>
                    <p className="nc2-muted">Като основание за плащане въведете номера на поръчката, който ще видите веднага след завършване.</p>
                  </div>
                )}
                <div className="hidden">
                </div>
              </div>

              <div className="nc2-right">
                <h2 className="nc2-sec-title">Вашата поръчка</h2>
                <div className="nc2-items">
                  {items.map((it) => (
                    <div key={it.variant_sku} className="nc2-line" data-testid={`pc-line-${it.variant_sku}`}>
                      <img src={img(it.image, 160)} alt="" className="nc2-line-img" />
                      <div className="nc2-line-mid">
                        <p className="nc2-line-tit">{it.title}</p>
                        <p className="nc2-line-var">{it.variant_name}</p>
                        <div className="nc2-qty">
                          <button type="button" onClick={() => updateQty(it.variant_sku, Math.max(1, it.quantity - 1))} aria-label="−"><Minus className="h-4 w-4" /></button>
                          <span data-testid={`pc-qty-${it.variant_sku}`}>{it.quantity}</span>
                          <button type="button" onClick={() => updateQty(it.variant_sku, it.quantity + 1)} aria-label="+"><Plus className="h-4 w-4" /></button>
                          <button type="button" className="nc2-line-rm" onClick={() => remove(it.variant_sku)} aria-label="Премахни"><Trash2 className="h-4 w-4" /></button>
                        </div>
                      </div>
                      <span className="nc2-line-price">{fmtEUR(it.price_eur * it.quantity)}</span>
                    </div>
                  ))}
                </div>

                <div className="nc2-disco">
                  <input className="nc2-inp" placeholder="Код за отстъпка" value={code}
                    onChange={(e) => setCode(e.target.value)} data-testid="pc-discount-code" />
                  <button type="button" className="nc2-apply" onClick={applyCode} data-testid="pc-discount-apply">Приложи</button>
                </div>

                <div className="nc2-sum">
                  <div className="nc2-sum-row"><span>Междинна сума</span><span>{fmtEUR(subtotal)}</span></div>
                  {discountAmount > 0 && (
                    <div className="nc2-sum-row"><span>Отстъпка {discount?.code}</span><span className="text-emerald-700">− {fmtEUR(discountAmount)}</span></div>
                  )}
                  <div className="nc2-sum-row">
                    <span>Доставка{method ? ` · ${BG_PROVIDER[method.provider_key] || method.provider_name}` : ""}</span>
                    <span>{method ? fmtEUR(method.price_amount) : "—"}</span>
                  </div>
                  <div className="nc2-sum-row nc2-sum-total"><strong>Общо</strong><strong data-testid="pc-total">{fmtEUR(total)}</strong></div>
                  {showsBGN() && <p className="nc2-muted text-right">{fmtBGN(total)}</p>}
                </div>

                <button type="button" className="nc2-cta" disabled={!ready || busy} onClick={placeOrder} data-testid="pc-continue">
                  {busy ? "Изпращане…" : `Завърши поръчката · ${fmtEUR(total)}`}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
