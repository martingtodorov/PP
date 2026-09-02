/**
 * Logical navigation targets. Components ask for a key ("terms", "catalog", "retatrutide") and the
 * backend (/api/links) tells us the path that exists right now, so renaming a page or a collection
 * cannot break the navigation. The defaults keep the UI intact before the first response.
 */
const DEFAULTS = {
  catalog: "/collections/2all-the-peptides-1",
  retatrutide: "/collections/retatrutide-price",
  terms: "/pages/terms-conditions",
  privacy: "/pages/privacy-policy",
  cookies: "/pages/cookies",
  refund: "/pages/refund-policy",
  shipping: "/pages/delivery-and-payment",
  faq: "/pages/faq",
  contacts: "/pages/contact-1",
  about: "/pages/about-1",
  whatArePeptides: "/pages/какво-са-пептиди",
  chemicalAnalysis: "/pages/chemical-analysis",
  scientificLiterature: "/pages/scientific-literature",
  partners: "/pages/become-a-distributor",
  articles: "/pages/articles",
};

let resolved = { ...DEFAULTS };

export const setLinks = (data) => {
  resolved = { ...DEFAULTS, ...(data || {}) };
};

export const link = (key) => resolved[key] || DEFAULTS[key] || "/";
