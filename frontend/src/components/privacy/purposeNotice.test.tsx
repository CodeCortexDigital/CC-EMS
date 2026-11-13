// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock('@/services/privacy.service', () => ({
  errorText: (e: any, fallback: string) => e?.response?.data?.error || fallback,
  default: {
    requests: vi.fn().mockResolvedValue({ results: [], statuses: {} }), consentTypes: vi.fn().mockResolvedValue([]), consentReport: vi.fn().mockResolvedValue({}),
    register: vi.fn().mockResolvedValue({ entries: [], school: '' }),
    documents: vi.fn(), noticeDraft: vi.fn(), ensureSensitiveConsent: vi.fn(), publishNotice: vi.fn(), noticeDelivery: vi.fn(), noticeDeliveryCsv: vi.fn(),
  },
}));

import privacy from '@/services/privacy.service';
import PrivacyAdminPanel from './PrivacyAdminPanel';
import NoticeDelivery from './NoticeDelivery';

const p = privacy as unknown as Record<string, ReturnType<typeof vi.fn>>;
const school = { id: 'd1', kind: 'school_privacy', version: 1, title: '若葉学園のお知らせ', body: '...', published_at: '2026-11-01T00:00:00Z', school: 'Wakaba', accepted: 3, people: 10 };
const docs = (over = {}) => ({ documents: [school], template: { title: 'T', body: 'B' }, history: [], register_newer: false, ...over });
const draft = (over = {}) => ({ title: '若葉学園 個人情報の利用目的のお知らせ', body: '■ 健康情報【要配慮個人情報】\n  利用目的: 生徒の安全', entries: 13, sensitive: 4,
                                 consent: { needed: true, exists: false, label: '' }, ...over });

beforeEach(() => {
  vi.clearAllMocks(); cleanup(); document.documentElement.lang = 'ja';
  p.documents.mockResolvedValue(docs());
  p.noticeDelivery.mockResolvedValue({ document: null, rows: [], summary: { people: 0, read: 0, not_read: 0 } });
});

describe('Notice drafted from the register', () => {
  it('fills the editor from the register in the page language', async () => {
    p.noticeDraft.mockResolvedValue(draft());
    render(<PrivacyAdminPanel />);
    fireEvent.click(await screen.findByText('Draft the notice from the data handling register'));
    await waitFor(() => expect(p.noticeDraft).toHaveBeenCalledWith('ja'));
    expect((await screen.findByLabelText('Notice text') as HTMLTextAreaElement).value).toContain('【要配慮個人情報】');
    expect((screen.getAllByLabelText('Title')[0] as HTMLInputElement).value).toBe('若葉学園 個人情報の利用目的のお知らせ');
  });

  it('offers the consent question for sensitive information, once', async () => {
    p.noticeDraft.mockResolvedValue(draft());
    p.ensureSensitiveConsent.mockResolvedValue({ created: true, consent: { id: 'c1', label: '要配慮個人情報' } });
    render(<PrivacyAdminPanel />);
    fireEvent.click(await screen.findByText('Draft the notice from the data handling register'));
    fireEvent.click(await screen.findByText('Add the consent question for sensitive information'));
    await waitFor(() => expect(p.ensureSensitiveConsent).toHaveBeenCalledWith('ja'));
    await waitFor(() => expect(screen.queryByText('Add the consent question for sensitive information')).toBeNull());
  });

  it('does not offer it when the question exists or nothing is sensitive', async () => {
    p.noticeDraft.mockResolvedValue(draft({ consent: { needed: true, exists: true, label: 'x' } }));
    render(<PrivacyAdminPanel />);
    fireEvent.click(await screen.findByText('Draft the notice from the data handling register'));
    await screen.findByLabelText('Notice text');
    expect(screen.queryByText('Add the consent question for sensitive information')).toBeNull();
  });

  it('says why when the register is empty', async () => {
    const { toast } = await import('sonner');
    p.noticeDraft.mockRejectedValue({ response: { data: { error: 'The data handling register is empty.' } } });
    render(<PrivacyAdminPanel />);
    fireEvent.click(await screen.findByText('Draft the notice from the data handling register'));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('The data handling register is empty.'));
  });

  it('warns when the register changed after the notice was published', async () => {
    p.documents.mockResolvedValue(docs({ register_newer: true }));
    render(<PrivacyAdminPanel />);
    expect(await screen.findByText(/The data handling register was changed after this notice was published/)).toBeTruthy();
  });
});

describe('Who has read the notice', () => {
  const data = () => ({
    document: { title: '若葉学園のお知らせ', version: 2, published_at: '2026-11-01T00:00:00Z' }, summary: { people: 2, read: 1, not_read: 1 },
    rows: [{ user_id: 'u1', name: '山田 花子', email: 'hana@a.test', role: 'Parent', children: '山田 太郎', read: false, read_at: null },
           { user_id: 'u2', name: '佐藤 一郎', email: 'ichiro@a.test', role: 'Parent', children: '佐藤 次郎', read: true, read_at: '2026-11-05T09:00:00Z' }],
  });

  it('is hidden until a notice has been published', async () => {
    const { container } = render(<NoticeDelivery />);
    await waitFor(() => expect(p.noticeDelivery).toHaveBeenCalledWith('parents'));
    expect(container.textContent).toBe('');
  });

  it('shows the families who have not read it first, with their children', async () => {
    p.noticeDelivery.mockResolvedValue(data());
    render(<NoticeDelivery />);
    expect(await screen.findByText('山田 花子')).toBeTruthy();
    expect(screen.getByText('山田 太郎')).toBeTruthy();
    expect(screen.getByText('Not yet')).toBeTruthy();
    expect(screen.queryByText('佐藤 一郎')).toBeNull();                         // only those who have not read it, by default
    expect(screen.getByText(/have read it/).textContent).toContain('1');
  });

  it('can show everyone, switch group, and download', async () => {
    p.noticeDelivery.mockResolvedValue(data());
    p.noticeDeliveryCsv.mockResolvedValue(undefined);
    render(<NoticeDelivery />);
    fireEvent.click(await screen.findByLabelText(/Only those who have not read it/));
    expect(await screen.findByText('佐藤 一郎')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Who'), { target: { value: 'staff' } });
    await waitFor(() => expect(p.noticeDelivery).toHaveBeenCalledWith('staff'));
    fireEvent.click(await screen.findByText('CSV'));
    await waitFor(() => expect(p.noticeDeliveryCsv).toHaveBeenCalledWith('staff'));
  });
});
