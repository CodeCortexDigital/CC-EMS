import { describe, expect, it } from 'vitest';
import { eraYear, wareki, warekiSchoolYear } from './wareki';

describe('Japanese era dates', () => {
  it('writes Reiwa, Heisei and Showa dates, with 元年 for the first year', () => {
    expect(wareki('2026-04-06')).toBe('令和8年4月6日');
    expect(wareki('2019-05-01')).toBe('令和元年5月1日');
    expect(wareki('2019-04-30')).toBe('平成31年4月30日');
    expect(wareki('1989-01-07')).toBe('昭和64年1月7日');
    expect(wareki('1989-01-08')).toBe('平成元年1月8日');
  });
  it('gives the school year and handles empty or very old dates', () => {
    expect(warekiSchoolYear('2026-04-06')).toBe('令和8年度');
    expect(wareki(null)).toBe('');
    expect(wareki('')).toBe('');
    expect(wareki('1900-02-03')).toBe('1900年2月3日');
    expect(eraYear('2020-01-01')).toEqual({ era: '令和', year: '2' });
  });
});
