// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import DemoBanner from './DemoBanner';

afterEach(() => { cleanup(); vi.unstubAllEnvs(); });

describe('Demonstration site label', () => {
  it('says the data is made up on a demonstration site', () => {
    vi.stubEnv('VITE_DEMO_LOGINS', 'true');
    render(<DemoBanner />);
    expect(screen.getByRole('note').textContent).toMatch(/Sample data: every student, staff member and figure here is made up/);
  });

  it('can carry the wording of a site made for one school', () => {
    vi.stubEnv('VITE_DEMO_LOGINS', 'true');
    vi.stubEnv('VITE_DEMO_LABEL', 'デモ環境: 氏名・数値はすべてサンプルです。');
    render(<DemoBanner />);
    expect(screen.getByRole('note').textContent).toBe('デモ環境: 氏名・数値はすべてサンプルです。');
  });

  it('is not shown on a live site', () => {
    vi.stubEnv('VITE_DEMO_LOGINS', 'false');
    const { container } = render(<DemoBanner />);
    expect(container.textContent).toBe('');
  });
});
