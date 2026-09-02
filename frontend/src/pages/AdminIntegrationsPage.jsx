import AdminLayout from "../components/AdminLayout";
import { NextLevelCard } from "../components/admin/NextLevelCard";
import { FulfillmentCard } from "../components/admin/FulfillmentCard";

export default function AdminIntegrationsPage() {
  return (
    <AdminLayout title="Интеграции">
      <FulfillmentCard />
      <NextLevelCard />
    </AdminLayout>
  );
}
