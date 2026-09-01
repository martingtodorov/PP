/* global self, clients */
/* PurePeptide admin push notifications */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: "PurePeptide", body: event.data ? event.data.text() : "Ново събитие" };
  }

  event.waitUntil(
    self.registration.showNotification(data.title || "PurePeptide", {
      body: data.body || "Ново събитие в магазина",
      icon: "/logo192.png",
      badge: "/logo192.png",
      tag: data.tag || "purepeptide",
      data: { url: data.url || "/admin/orders" },
      requireInteraction: true,
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/admin/orders", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      const existing = list.find((c) => c.url.startsWith(self.location.origin));
      if (existing) {
        existing.navigate(target);
        return existing.focus();
      }
      return self.clients.openWindow(target);
    })
  );
});
