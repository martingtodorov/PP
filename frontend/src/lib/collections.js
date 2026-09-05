// The "Всички пептиди" catch-all collection. `link_key: "catalog"` is set in the admin and survives
// every handle change or URL rotation — the handles are only a fallback for older databases.
export const ALL_COLLECTION = "2all-the-peptides-1";
const ALL_HANDLES = [ALL_COLLECTION, "all-peptides"];

export const isAllCollection = (c) =>
  c?.link_key === "catalog"
  || ALL_HANDLES.includes(c?.base_handle)
  || ALL_HANDLES.includes(c?.handle);
