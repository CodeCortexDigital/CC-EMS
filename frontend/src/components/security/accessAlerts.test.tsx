// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/security.service', () => ({
  default: { accessAlerts: vi.fn(), saveAlertLimits: vi.fn(), updateAlert: vi.fn(), alertReport: vi.fn() },
}));

import security from '@/services/security.service';
import AccessAlerts from './AccessAlerts';

const m = security as unknown as Record<string, ReturnType<typeof vi.fn>>;
const limits = { views: 30, night_views: 5, exports: 5, refused: 10 };
const alert = (over = {}) => ({
  id: 'a1', kind: 'bulk_views', kind_label: 'Many student records opened', who: '佐藤 花', email: 'sato@a.test', window_start: '2026-11-10T12:00:00+09:00',
  window_end: '2026-11-10T12:29:00+09:00', count: 30, limit: 30, status: 'open', status_label: 'To review', note: '', reviewed_by: '', reviewed_at: null,
  created_at: '2026-11-10T13:00:00+09:00', ...over,
});
const list = (results: any[]) => ({ results, open: results.filter((r) => r.status === 'open').length, new: 0, limits, defaults: limits, kinds: {} });
const draft = { title: '個人データの漏えい等のおそれに関する報告(速報)(案)', sections: [{ heading: '概要', text: '佐藤 花が30名分の生徒記録を閲覧した。' }, { heading: '原因', text: '調査中(要確認)' }],
                guidance: ['報告の期限の目安: 速報は概ね3〜5日以内'], note: 'この文書は下書きです。', school: '若葉学園', prepared_on: '2026-11-12', alert: 'a1' };

beforeEach(() => { vi.clearAllMocks(); cleanup(); m.accessAlerts.mockResolvedValue(list([alert()])); });

describe('Alerts for unusual use', () => {
  it('lists the alerts with who, how many and the state', async () => {
    render(<AccessAlerts />);
    expect(await screen.findByText('Many student records opened')).toBeTruthy();
    expect(screen.getByText(/佐藤 花/)).toBeTruthy();
    expect(screen.getByText('To review')).toBeTruthy();
    expect(screen.getByText(/30 \(limit 30\)/)).toBeTruthy();
  });

  it('says so when there are none', async () => {
    m.accessAlerts.mockResolvedValue(list([]));
    render(<AccessAlerts />);
    expect(await screen.findByText('No alerts.')).toBeTruthy();
  });

  it('needs a note before an alert is marked reviewed', async () => {
    m.updateAlert.mockResolvedValue(alert({ status: 'reviewed' }));
    render(<AccessAlerts />);
    fireEvent.click(await screen.findByText('Reviewed: record what I found'));
    const save = screen.getByText('Save');
    expect(save).toHaveProperty('disabled', true);
    fireEvent.change(screen.getByLabelText('What you found'), { target: { value: '進路指導の準備でした' } });
    fireEvent.click(save);
    await waitFor(() => expect(m.updateAlert).toHaveBeenCalledWith('a1', 'reviewed', '進路指導の準備でした'));
  });

  it('shows a decided alert with its note and lets it be re-opened', async () => {
    m.accessAlerts.mockResolvedValue(list([alert({ status: 'dismissed', status_label: 'Not a problem', note: '面談の準備', reviewed_by: 'Head' })]));
    m.updateAlert.mockResolvedValue(alert());
    render(<AccessAlerts />);
    expect(await screen.findByText(/面談の準備/)).toBeTruthy();
    fireEvent.click(screen.getByText('Re-open'));
    await waitFor(() => expect(m.updateAlert).toHaveBeenCalledWith('a1', 'open', ''));
  });

  it('opens the draft report in Japanese and in English', async () => {
    m.alertReport.mockResolvedValue(draft);
    render(<AccessAlerts />);
    fireEvent.click(await screen.findByText(/Draft report \(日本語\)/));
    await waitFor(() => expect(m.alertReport).toHaveBeenCalledWith('a1', 'ja'));
    expect(await screen.findByText('佐藤 花が30名分の生徒記録を閲覧した。')).toBeTruthy();
    expect(screen.getByText('調査中(要確認)')).toBeTruthy();
    expect(screen.getByText(/速報は概ね3〜5日以内/)).toBeTruthy();
    fireEvent.click(screen.getByText('Close'));
    fireEvent.click(screen.getByText('Draft report (English)'));
    await waitFor(() => expect(m.alertReport).toHaveBeenCalledWith('a1', 'en'));
  });

  it('saves new limits', async () => {
    m.saveAlertLimits.mockResolvedValue({ ...list([alert()]), limits: { ...limits, views: 10 } });
    render(<AccessAlerts />);
    fireEvent.click(await screen.findByText('When alerts are raised'));
    fireEvent.change(screen.getByLabelText('Different student records opened in one hour'), { target: { value: '10' } });
    fireEvent.click(screen.getByText('Save the limits'));
    await waitFor(() => expect(m.saveAlertLimits).toHaveBeenCalledWith({ ...limits, views: 10 }));
  });
});
