import { afterEach, describe, expect, it, vi } from 'vitest';
import { browserTimezone, guessCurrency } from './guessCurrency';

afterEach(() => vi.restoreAllMocks());

describe('new-school suggestions', () => {
  it('falls back to dollars, not rupees, when nothing can be guessed', () => {
    vi.spyOn(Intl, 'DateTimeFormat').mockImplementation(() => ({ resolvedOptions: () => ({ timeZone: '' }) }) as unknown as Intl.DateTimeFormat);
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue([]);
    expect(guessCurrency(['USD', 'PKR', 'EUR'])).toBe('USD');
  });

  it('still suggests the visitor\'s own currency when it can tell', () => {
    vi.spyOn(Intl, 'DateTimeFormat').mockImplementation(() => ({ resolvedOptions: () => ({ timeZone: 'Europe/London' }) }) as unknown as Intl.DateTimeFormat);
    expect(guessCurrency(['USD', 'GBP'])).toBe('GBP');
  });

  it('falls back to a U.S. time zone when the browser will not say', () => {
    vi.spyOn(Intl, 'DateTimeFormat').mockImplementation(() => { throw new Error('no'); });
    expect(browserTimezone()).toBe('America/New_York');
  });
});
