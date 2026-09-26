/** Imported copy sometimes carries its own <h1> — one H1 per page, the rest become H2. */
export const demoteHeadings = (markup) =>
  String(markup || "")
    .replace(/<h1(\s[^>]*)?>/gi, "<h2>")
    .replace(/<\/h1>/gi, "</h2>");

const plain = (s) => String(s || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().toLowerCase();

/** Imported copy carries empty `<img>` tags and `alt=""`: drop the sourceless ones, describe the rest. */
export const fixImages = (markup, title = "") => {
  const label = String(title || "").replace(/"/g, "&quot;").trim();
  return String(markup || "")
    .replace(/<img(?![^>]*\ssrc\s*=)[^>]*>/gi, "")
    .replace(/<img\b[^>]*>/gi, (tag) => {
      if (/\salt\s*=\s*"[^"]+"/i.test(tag) || !label) return tag;
      return tag.replace(/\salt\s*=\s*"[^"]*"/i, "").replace(/\s*\/?>$/, ` alt="${label}">`);
    });
};

/** Drops the opening heading of the copy when it only repeats the page H1 (no title twice). */
export const dropLeadingHeading = (markup, heading) => {
  if (!markup || !heading) return markup;
  return String(markup).replace(
    /^\s*<h[1-3](\s[^>]*)?>([\s\S]*?)<\/h[1-3]>/i,
    (match, _attrs, inner) => (plain(inner) === plain(heading) ? "" : match),
  );
};
