// The "Всички пептиди" catch-all collection. Two handles exist in the wild: the Shopify one the
// backend canonicalises to, and the legacy seed handle still used by older databases.
export const ALL_COLLECTION = "2all-the-peptides-1";
const ALL_HANDLES = [ALL_COLLECTION, "all-peptides"];

export const isAllCollection = (c) =>
  ALL_HANDLES.includes(c.base_handle || c.handle) || ALL_HANDLES.includes(c.handle);
