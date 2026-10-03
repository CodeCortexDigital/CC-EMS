// Account Settings card: install the app on this device and choose which notifications are pushed to it.
import { useCallback, useEffect, useState } from 'react';
import { BellRing, Smartphone, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import push, { PushDevice, PushState, PushType } from '@/services/push.service';
import { canInstall, isInstalled, isIos, onInstallChange, promptInstall } from '@/utils/pwa';
import { btn, btnGhost, card, errorText, fmtDateTime, Pill } from '@/components/common/kit';

const STATE_TEXT: Record<PushState, string> = {
  unsupported: 'This browser cannot receive push notifications. On an iPhone or iPad, add the app to your Home Screen first.',
  unavailable: 'Push notifications are not switched on for this school yet.',
  blocked: 'Notifications are blocked for this site. Allow them in your browser settings, then come back.',
  off: 'Notifications are off on this device.',
  on: 'Notifications are on for this device.',
};

export default function AppAndNotifications() {
  const [state, setState] = useState<PushState | null>(null);
  const [devices, setDevices] = useState<PushDevice[]>([]);
  const [types, setTypes] = useState<PushType[]>([]);
  const [busy, setBusy] = useState(false);
  const [installable, setInstallable] = useState(canInstall());

  useEffect(() => onInstallChange(() => setInstallable(canInstall())), []);

  const load = useCallback(async () => {
    try {
      const s = await push.state();
      setState(s);
      if (s !== 'unavailable') {
        const [d, t] = await Promise.all([push.devices(), push.types()]);
        setDevices(d); setTypes(t);
      }
    } catch { setState('unavailable'); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const toggle = async () => {
    setBusy(true);
    try {
      if (state === 'on') { await push.disable(); toast.success('Notifications turned off on this device.'); }
      else { await push.enable(); toast.success('Notifications turned on.'); }
      await load();
    } catch (e) { toast.error(errorText(e, (e as Error)?.message || 'Could not change notifications.')); } finally { setBusy(false); }
  };

  const flip = async (key: string) => {
    const muted = types.filter((t) => !t.enabled).map((t) => t.key);
    const next = muted.includes(key) ? muted.filter((k) => k !== key) : [...muted, key];
    try { setTypes(await push.saveMuted(next)); } catch (e) { toast.error(errorText(e, 'Could not save.')); }
  };

  const install = async () => { if (await promptInstall()) toast.success('Installed. Look for the app on your home screen.'); };

  return (
    <div className={card} aria-label="App and notifications">
      <h2 className="font-bold text-sm mb-1 flex items-center gap-2"><Smartphone className="w-4 h-4 text-emerald-700" />App and notifications</h2>
      <p className="text-xs text-slate-500 mb-3">Install the school portal on your phone or computer, and get alerts even when it is closed.</p>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        {isInstalled() ? <Pill tone="green">Installed on this device</Pill>
          : installable ? <button className={btn} onClick={install}>Install the app</button>
          : <span className="text-xs text-slate-500">{isIos() ? 'To install: tap Share, then Add to Home Screen.' : 'Your browser offers install from its menu when the app can be installed.'}</span>}
      </div>

      {state === null ? <p className="text-sm text-slate-400">Checking…</p> : (
        <>
          <div className="flex flex-wrap items-center gap-3 mb-3">
            <BellRing className="w-4 h-4 text-slate-500" />
            <span className="text-sm text-slate-700 mr-auto max-w-xl">{STATE_TEXT[state]}</span>
            {(state === 'off' || state === 'on') && (
              <button className={state === 'on' ? btnGhost : btn} disabled={busy} onClick={toggle}>{state === 'on' ? 'Turn off' : 'Turn on'}</button>
            )}
            {state === 'on' && <button className={btnGhost} onClick={async () => { const n = await push.sendTest().catch(() => 0); toast[n ? 'success' : 'error'](n ? 'Test sent.' : 'Could not reach this device.'); }}>Send a test</button>}
          </div>

          {state !== 'unavailable' && types.length > 0 && (
            <fieldset className="mb-3">
              <legend className="text-xs font-bold text-slate-600 mb-1">Send me notifications about</legend>
              <div className="flex flex-wrap gap-x-5 gap-y-1">
                {types.map((t) => (
                  <label key={t.key} className="flex items-center gap-1.5 text-sm text-slate-700">
                    <input type="checkbox" checked={t.enabled} onChange={() => flip(t.key)} aria-label={t.label} /> {t.label}
                  </label>
                ))}
              </div>
            </fieldset>
          )}

          {devices.length > 0 && (
            <div>
              <p className="text-xs font-bold text-slate-600 mb-1">Devices that get notifications</p>
              <ul className="divide-y divide-slate-100 text-sm">
                {devices.map((d) => (
                  <li key={d.id} className="py-1.5 flex items-center gap-2">
                    <span className="mr-auto">{d.platform} <span className="text-slate-400">· added {fmtDateTime(d.added)}</span></span>
                    <button aria-label={`Remove ${d.platform} device`} className="text-slate-400 hover:text-rose-600"
                      onClick={async () => { await push.removeDevice(d.id).catch(() => undefined); load(); }}><Trash2 className="w-4 h-4" /></button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
