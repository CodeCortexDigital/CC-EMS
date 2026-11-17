import { describe, expect, it } from 'vitest';

describe('demo school on the sign-in page', { timeout: 30000 }, () => {
  it('offers only the US school, whatever the build settings', async () => {
    const { DEMO_SCHOOLS } = await import('./LoginPage');
    expect(DEMO_SCHOOLS.map((d) => d.key)).toEqual(['us']);
    expect(DEMO_SCHOOLS[0].logins[0].email).toBe('admin@code.com');
    expect(DEMO_SCHOOLS[0].language).toBe('en');
  });
});
