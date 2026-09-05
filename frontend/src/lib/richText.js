/** Imported copy sometimes carries its own <h1> — one H1 per page, the rest become H2. */
export const demoteHeadings = (markup) =>
  String(markup || "")
    .replace(/<h1(\s[^>]*)?>/gi, "<h2>")
    .replace(/<\/h1>/gi, "</h2>");
