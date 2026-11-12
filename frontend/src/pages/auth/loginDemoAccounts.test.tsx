import { afterEach, describe, expect, it, vi } from 'vitest';

describe('demo schools on the sign-in page', { timeout: 30000 }, () => {
  afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

  it('offers only the US school by default', async () => {
    const { DEMO_SCHOOLS } = await import('./LoginPage');
    expect(DEMO_SCHOOLS.map((d) => d.key)).toEqual(['us']);
    expect(DEMO_SCHOOLS[0].logins[0].email).toBe('admin@code.com');
  });

  it('offers a Japanese school too when its administrator is given', async () => {
    vi.resetModules();
    vi.stubEnv('VITE_DEMO_ADMIN_EMAIL', 'masato@admin.com');
    vi.stubEnv('VITE_DEMO_ADMIN_PASSWORD', 'a-private-password');
    vi.stubEnv('VITE_DEMO_ADMIN_LABEL', 'Admin (Masato)');
    const { DEMO_SCHOOLS } = await import('./LoginPage');
    expect(DEMO_SCHOOLS.map((d) => d.key)).toEqual(['us', 'jp']);
    const jp = DEMO_SCHOOLS[1];
    expect(jp.language).toBe('ja');
    expect(jp.logins[0]).toMatchObject({ email: 'masato@admin.com', password: 'a-private-password', label: 'Admin (Masato)', role: 'admin' });
    expect(jp.logins.map((a) => a.email)).toContain('teacher@wakaba.example');
    expect(DEMO_SCHOOLS[0].logins.map((a) => a.email)).not.toContain('masato@admin.com');
  });

  it('can offer the Japanese school without an administrator password', async () => {
    vi.resetModules();
    vi.stubEnv('VITE_DEMO_JAPAN_SCHOOL', 'true');
    const { DEMO_SCHOOLS } = await import('./LoginPage');
    expect(DEMO_SCHOOLS.map((d) => d.key)).toEqual(['us', 'jp']);
    expect(DEMO_SCHOOLS[1].logins.map((a) => a.label)).toEqual(['Teacher', 'Parent', 'Student']);
  });

  it('a Japanese-only site shows only the Japanese school', async () => {
    vi.resetModules();
    vi.stubEnv('VITE_DEMO_ADMIN_EMAIL', 'masato@admin.com');
    vi.stubEnv('VITE_DEMO_ADMIN_PASSWORD', 'a-private-password');
    vi.stubEnv('VITE_DEMO_ADMIN_REPLACE', 'true');
    const { DEMO_SCHOOLS } = await import('./LoginPage');
    expect(DEMO_SCHOOLS.map((d) => d.key)).toEqual(['jp']);
  });
});
