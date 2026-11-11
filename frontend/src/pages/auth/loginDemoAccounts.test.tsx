import { afterEach, describe, expect, it, vi } from 'vitest';

describe('demo accounts on the sign-in page', { timeout: 30000 }, () => {
  afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

  it('lists the public administrator by default', async () => {
    const { DEMO_LOGINS } = await import('./LoginPage');
    expect(DEMO_LOGINS[0].email).toBe('admin@code.com');
    expect(DEMO_LOGINS.map((a) => a.email)).toContain('teacher@code.com');
  });

  it("a client's own administrator takes the place of the public one", async () => {
    vi.resetModules();
    vi.stubEnv('VITE_DEMO_ADMIN_EMAIL', 'masato@admin.com');
    vi.stubEnv('VITE_DEMO_ADMIN_PASSWORD', 'a-private-password');
    vi.stubEnv('VITE_DEMO_ADMIN_LABEL', 'Admin (Masato)');
    const { DEMO_LOGINS } = await import('./LoginPage');
    expect(DEMO_LOGINS[0]).toMatchObject({ email: 'masato@admin.com', password: 'a-private-password', label: 'Admin (Masato)', role: 'admin' });
    expect(DEMO_LOGINS.map((a) => a.email)).not.toContain('admin@code.com');
    expect(DEMO_LOGINS).toHaveLength(4);
  });

  it('needs both the email and the password', async () => {
    vi.resetModules();
    vi.stubEnv('VITE_DEMO_ADMIN_EMAIL', 'masato@admin.com');
    const { DEMO_LOGINS } = await import('./LoginPage');
    expect(DEMO_LOGINS[0].email).toBe('admin@code.com');
  });
});
