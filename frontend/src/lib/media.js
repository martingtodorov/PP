/* Brand assets (logo, OG image, icon) live in our own object storage.
   Populated from /api/settings once, readable from non-React modules (seo, schema). */
let media = {};
let shipping = null;

export const setSiteMedia = (next) => {
  media = next || {};
};

export const siteMedia = (key, fallback = "") => media[key] || fallback;

/* Delivery summary for the current storefront (country, price, handling/transit days, return
   window) — Google's merchant listings require it inside the product offer. */
export const setShippingInfo = (next) => {
  shipping = next || null;
};

export const shippingInfo = () => shipping;
