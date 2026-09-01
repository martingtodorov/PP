/* Brand assets (logo, OG image, icon) live in our own object storage.
   Populated from /api/settings once, readable from non-React modules (seo, schema). */
let media = {};

export const setSiteMedia = (next) => {
  media = next || {};
};

export const siteMedia = (key, fallback = "") => media[key] || fallback;
