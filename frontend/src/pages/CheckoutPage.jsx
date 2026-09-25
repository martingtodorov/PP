import Layout from "../components/Layout";
import CheckoutFlow from "../components/CheckoutFlow";
import { useSeo } from "../lib/seo";
import { useLocaleCtx } from "../i18n/LocaleContext";

/** The accelerated checkout lives on its own route — the cart no longer opens it in a modal. */
export default function CheckoutPage() {
  const { t } = useLocaleCtx();
  useSeo({
    title: `${t("seoCheckoutTitle")}`,
    description: t("seoCheckoutDesc"),
    path: "/checkout",
    robots: "noindex,nofollow",
  });

  return (
    <Layout>
      <CheckoutFlow />
    </Layout>
  );
}
