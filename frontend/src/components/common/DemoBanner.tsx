/** A demonstration site says so on every screen. Shown only when the build sets VITE_DEMO_LOGINS=true (never on a live school's site).
 *  VITE_DEMO_LABEL replaces the wording, for example for a site made for one school. */
export const isDemoSite = () => import.meta.env.VITE_DEMO_LOGINS === 'true';

export default function DemoBanner() {
  if (!isDemoSite()) return null;
  const label = String(import.meta.env.VITE_DEMO_LABEL || '').trim()
    || 'Sample data: every student, staff member and figure here is made up for demonstration.';
  return <p role="note" aria-label="Demonstration site" className="bg-amber-50 px-3 py-1 text-center text-xs font-medium text-amber-900 print:hidden">{label}</p>;
}
