// Japanese era dates (和暦) for the records Japanese schools keep: 2026-04-06 is 令和8年4月6日.
const ERAS: Array<{ name: string; from: string }> = [
  { name: '令和', from: '2019-05-01' }, { name: '平成', from: '1989-01-08' }, { name: '昭和', from: '1926-12-25' },
];

/** The era and year of an ISO date (year 1 is written 元年 when `gan` is true). Dates before 1926 fall back to the western year. */
export function eraYear(iso: string | null | undefined, gan = false): { era: string; year: string } | null {
  if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return null;
  const day = iso.slice(0, 10);
  const era = ERAS.find((e) => day >= e.from);
  if (!era) return { era: '', year: `${Number(day.slice(0, 4))}` };
  const y = Number(day.slice(0, 4)) - Number(era.from.slice(0, 4)) + 1;
  return { era: era.name, year: y === 1 && gan ? '元' : String(y) };
}

/** 令和8年4月6日 */
export function wareki(iso: string | null | undefined): string {
  if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return '';
  const e = eraYear(iso, true);
  const m = Number(iso.slice(5, 7));
  const d = Number(iso.slice(8, 10));
  return e && e.era ? `${e.era}${e.year}年${m}月${d}日` : `${Number(iso.slice(0, 4))}年${m}月${d}日`;
}

/** 令和8年度 for a school year that starts on this date (the Japanese school year begins in April). */
export function warekiSchoolYear(startIso: string | null | undefined): string {
  const e = eraYear(startIso, true);
  return e && e.era ? `${e.era}${e.year}年度` : '';
}
