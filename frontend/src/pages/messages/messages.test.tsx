// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const auth = vi.hoisted(() => ({ role: 'teacher' as string }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ role: auth.role, user: { id: 'u-green' } }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

import api from '@/services/api';
import MessagesPage from './MessagesPage';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;

const conv = (id: string, subject: string, urgency: string, at: string) => ({
  id, subject, student: null, participants: [{ id: 'u-p4', name: 'Parent Four', role: 'Parent' }],
  last_message: { body: 'hello', at, sender: 'Parent Four' }, last_message_at: at, unread: 1, urgency,
});
const thread = {
  ...conv('c1', 'Poster', 'normal', '2026-10-01T10:00:00Z'),
  messages: [{ id: 'm1', body: 'Can Kid bring a poster?', at: '2026-10-01T10:00:00Z', sender: { id: 'u-p4', name: 'Parent Four' }, attachment: null, urgency: 'normal' }],
};

function mockApi(list: unknown[]) {
  get.mockImplementation((url: string) => Promise.resolve({ data: /conversations\/c1\/$/.test(url) ? thread : list }));
}
const renderAt = (path = '/messages') => render(<MemoryRouter initialEntries={[path]}><MessagesPage /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks(); cleanup(); auth.role = 'teacher';
  Element.prototype.scrollIntoView = vi.fn();   // jsdom has none
});

describe('Messages inbox', () => {
  it('puts urgent and upset conversations first and says why', async () => {
    mockApi([conv('a', 'Newsletter', 'normal', '2026-10-03T10:00:00Z'), conv('b', 'Complaint', 'frustrated', '2026-10-02T10:00:00Z'), conv('c', 'Pickup', 'urgent', '2026-10-01T10:00:00Z')]);
    renderAt();
    await screen.findByText('Pickup');
    const subjects = screen.getAllByText(/Newsletter|Complaint|Pickup/).map((e) => e.textContent);
    expect(subjects).toEqual(['Pickup', 'Complaint', 'Newsletter']);
    expect(screen.getByText('Urgent')).toBeTruthy();
    expect(screen.getByText('Upset')).toBeTruthy();
  });

  it('shows no badge when nothing is pressing', async () => {
    mockApi([conv('a', 'Newsletter', 'normal', '2026-10-03T10:00:00Z')]);
    renderAt();
    await screen.findByText('Newsletter');
    expect(screen.queryByText('Urgent')).toBeNull();
    expect(screen.queryByText('Upset')).toBeNull();
  });
});

describe('A conversation', () => {
  beforeEach(() => mockApi([conv('c1', 'Poster', 'normal', '2026-10-01T10:00:00Z')]));

  it('translates a message, labels it machine translated and lets you flip back to the original', async () => {
    post.mockResolvedValue({ data: { translated_text: 'Peut-il apporter une affiche ?', language: 'fr', source: 'ai', cached: false } });
    renderAt('/messages?c=c1');
    await screen.findByText('Can Kid bring a poster?');
    fireEvent.click(screen.getByRole('button', { name: /Translate/ }));
    expect(await screen.findByText('Peut-il apporter une affiche ?')).toBeTruthy();
    expect(screen.getByText(/Machine translated/)).toBeTruthy();
    expect(screen.queryByText('Can Kid bring a poster?')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Show original' }));
    expect(screen.getByText('Can Kid bring a poster?')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Show translation' })).toBeTruthy();
  });

  it('puts a suggested reply in the reply box for the teacher to edit, and does not send it', async () => {
    post.mockResolvedValue({ data: { summary: 'Asks about a poster.', key_points: [], source: 'ai', suggested_reply: 'Any size is fine.' } });
    renderAt('/messages?c=c1');
    await screen.findByText('Can Kid bring a poster?');
    fireEvent.click(screen.getByRole('button', { name: /Summarise/ }));
    expect(await screen.findByText('Any size is fine.')).toBeTruthy();
    expect(screen.getByText(/read and edit it before you send/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Put in my reply box' }));
    expect((screen.getByLabelText('Reply') as HTMLTextAreaElement).value).toBe('Any size is fine.');
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));                    // only the summary call, nothing sent
    expect(post.mock.calls[0][0]).toMatch(/summarize/);
  });

  it('a parent can translate but gets no summary button on a short thread', async () => {
    auth.role = 'parent';
    renderAt('/messages?c=c1');
    await screen.findByText('Can Kid bring a poster?');
    expect(screen.queryByRole('button', { name: /Summarise/ })).toBeNull();
    expect(screen.getByRole('button', { name: /Translate/ })).toBeTruthy();
  });
});
