// Push notifications for the installed app: turn them on or off for this device, choose which kinds to receive.
import api from './api';

const base = '/auth/notifications';

export interface PushDevice { id: string; platform: string; user_agent: string; added: string; last_active: string }
export interface PushType { key: string; label: string; enabled: boolean }

/** The browser's public key arrives as base64url text; subscribing needs raw bytes. */
export function urlBase64ToUint8Array(value: string): Uint8Array {
  const padded = value + '='.repeat((4 - (value.length % 4)) % 4);
  const raw = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

export const pushSupported = (): boolean =>
  typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;

export type PushState = 'unsupported' | 'unavailable' | 'blocked' | 'off' | 'on';

const registration = async () => navigator.serviceWorker.ready;

const push = {
  /** Where this device stands: not supported, not set up by the school, blocked by the browser, off or on. */
  async state(): Promise<PushState> {
    if (!pushSupported()) return 'unsupported';
    const { data } = await api.get(`${base}/push/vapid-key/`);
    if (!data.enabled) return 'unavailable';
    if (Notification.permission === 'denied') return 'blocked';
    const sub = await (await registration()).pushManager.getSubscription();
    return sub && Notification.permission === 'granted' ? 'on' : 'off';
  },

  /** Ask permission, subscribe this device and register it. Throws a readable Error if it cannot. */
  async enable(): Promise<void> {
    if (!pushSupported()) throw new Error('This browser cannot receive push notifications.');
    const { data } = await api.get(`${base}/push/vapid-key/`);
    if (!data.enabled) throw new Error('Push notifications are not set up for this school yet.');
    if ((await Notification.requestPermission()) !== 'granted') throw new Error('Notifications are blocked. Allow them in your browser settings, then try again.');
    const reg = await registration();
    const sub = (await reg.pushManager.getSubscription())
      || (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(data.public_key) }));
    const json = sub.toJSON();
    await api.post(`${base}/push/subscribe/`, { endpoint: json.endpoint, keys: json.keys, userAgent: navigator.userAgent, platform: /android/i.test(navigator.userAgent) ? 'android' : /iphone|ipad/i.test(navigator.userAgent) ? 'ios' : 'web' });
  },

  async disable(): Promise<void> {
    const sub = await (await registration()).pushManager.getSubscription();
    if (!sub) return;
    await api.post(`${base}/push/unsubscribe/`, { endpoint: sub.endpoint });
    await sub.unsubscribe();
  },

  async devices(): Promise<PushDevice[]> { return (await api.get(`${base}/devices/`)).data.devices; },
  async removeDevice(id: string): Promise<void> { await api.delete(`${base}/devices/${id}/`); },
  async types(): Promise<PushType[]> { return (await api.get(`${base}/push/preferences/`)).data.types; },
  async saveMuted(muted: string[]): Promise<PushType[]> { return (await api.put(`${base}/push/preferences/`, { muted_types: muted })).data.types; },
  async sendTest(): Promise<number> { return (await api.post(`${base}/push/test/`)).data.sent; },
};

export default push;
