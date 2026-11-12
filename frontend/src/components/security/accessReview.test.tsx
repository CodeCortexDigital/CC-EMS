// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/security.service', () => ({ default: { accessReview: vi.fn(), exportAccessReview: vi.fn(), logPrint: vi.fn() } }));

import security from '@/services/security.service';
import AccessReviewPanel from './AccessReviewPanel';

const m = security as unknown as Record<string, ReturnType<typeof vi.fn>>;
const review = (over = {}) => ({
  days: 30, since: '2026-10-13', totals: { views: 12, exports: 2, prints: 3, refused: 1 },
  results: [
    { user_id: 'u1', who: '佐藤 花', email: 'sato@a.test', role: 'Teacher', views: 9, students_viewed: 7, exports: 0, prints: 3, refused: 0, last: '2026-11-11 09:10' },
    { user_id: 'u2', who: 'Head Teacher', email: 'head@a.test', role: 'Administrator', views: 3, students_viewed: 3, exports: 2, prints: 0, refused: 1, last: '2026-11-10 16:00' },
  ], ...over,
});

beforeEach(() => { vi.clearAllMocks(); cleanup(); m.accessReview.mockResolvedValue(review()); });

describe('Access review', () => {
  it('shows who opened, exported and printed records, busiest first, with totals', async () => {
    render(<AccessReviewPanel />);
    expect(await screen.findByText('佐藤 花')).toBeTruthy();
    const rows = screen.getAllByRole('row');
    expect(rows[1].textContent).toContain('sato@a.test');
    expect(rows[1].textContent).toContain('Teacher');
    expect(rows[rows.length - 1].textContent).toContain('Total');
    expect(rows[rows.length - 1].textContent).toContain('12');
    expect(m.accessReview).toHaveBeenCalledWith(30);
  });

  it('changes the period and exports to CSV for that period', async () => {
    m.exportAccessReview.mockResolvedValue(undefined);
    render(<AccessReviewPanel />);
    await screen.findByText('佐藤 花');
    fireEvent.change(screen.getByLabelText('Period'), { target: { value: '90' } });
    await waitFor(() => expect(m.accessReview).toHaveBeenCalledWith(90));
    fireEvent.click(await screen.findByText('CSV'));
    await waitFor(() => expect(m.exportAccessReview).toHaveBeenCalledWith(90));
  });

  it('says so when nothing was recorded', async () => {
    m.accessReview.mockResolvedValue(review({ results: [], totals: { views: 0, exports: 0, prints: 0, refused: 0 } }));
    render(<AccessReviewPanel />);
    expect(await screen.findByText('Nothing recorded in this period.')).toBeTruthy();
  });
});
