import { LOCALES } from "../i18n/locales";

/** XHR follows the API's real 301. Keep React's address/canonical in sync with its final response.
 * Ordinary 200 aliases and historical 404s are unchanged. Never redirect a newer navigation in
 * response to an obsolete request, nor navigate to an arbitrary external response origin.
 */
export const followRotation = (response, kind, requested, navigate) => {
  const finalUrl = response?.request?.responseURL;
  if (!finalUrl) return false;
  try {
    const final = new URL(finalUrl, window.location.origin).pathname.split("/").filter(Boolean);
    if (final.length !== 3 || final[0] !== "api" || final[1] !== kind) return false;
    const handle = decodeURIComponent(final[2]);
    if (handle === requested || handle.includes("/")) return false;
    const current = window.location.pathname.split("/").filter(Boolean);
    const prefix = LOCALES.includes(current[0]) ? `/${current.shift()}` : "";
    if (current.length !== 2 || current[0] !== kind || decodeURIComponent(current[1]) !== requested) return false;
    navigate(`${prefix}/${kind}/${final[2]}${window.location.search}${window.location.hash}`, { replace: true });
    return true;
  } catch {
    return false;
  }
};