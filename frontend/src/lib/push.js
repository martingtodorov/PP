import { api } from "./api";

const VAPID_PUBLIC_KEY = process.env.REACT_APP_VAPID_PUBLIC_KEY;

const toUint8Array = (base64) => {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const normalized = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(normalized);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
};

export const pushSupported = () =>
  "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

export const isStandalone = () =>
  window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;

export const isIOS = () => /iPad|iPhone|iPod/.test(navigator.userAgent);

export const registerPushWorker = async () => {
  if (!("serviceWorker" in navigator)) return null;
  return navigator.serviceWorker.register("/service-worker.js", { scope: "/" });
};

export const currentSubscription = async () => {
  if (!pushSupported()) return null;
  const reg = await navigator.serviceWorker.ready;
  return reg.pushManager.getSubscription();
};

export const subscribeAdmin = async () => {
  if (!pushSupported()) throw new Error("Този браузър не поддържа push нотификации");
  if (isIOS() && !isStandalone()) {
    throw new Error("На iPhone първо добавете сайта към Home Screen и го отворете от иконата");
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Нотификациите са блокирани в браузъра");

  await registerPushWorker();
  const reg = await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    const key = VAPID_PUBLIC_KEY || (await api.get("/push/public-key")).data.public_key;
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: toUint8Array(key),
    });
  }
  await api.post("/push/subscriptions", sub.toJSON());
  return sub;
};

export const unsubscribeAdmin = async () => {
  const sub = await currentSubscription();
  if (!sub) return;
  await api.delete("/push/subscriptions", { data: { endpoint: sub.endpoint } });
  await sub.unsubscribe();
};
