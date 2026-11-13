// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

let signedIn = { email: 'admin@us.test', full_name: 'US Admin' };
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ user: signedIn, role: 'admin', logout: vi.fn() }) }));
vi.mock('@/services/tenant.service', () => ({ default: { current: vi.fn() } }));
vi.mock('@/components/notifications/NotificationBell', () => ({ default: () => null }));
vi.mock('@/components/notifications/MessagesBadge', () => ({ default: () => null }));
vi.mock('@/components/search/CommandPalette', () => ({ default: () => null, useSearchShortcut: () => undefined }));
vi.mock('@/components/common/LanguagePicker', () => ({ LanguageMenuButton: () => null }));

import tenantService from '@/services/tenant.service';
import Header from './Header';

const current = tenantService.current as unknown as ReturnType<typeof vi.fn>;
const tenant = (name: string) => ({ name, settings_json: { institute_name: name } });
const show = () => render(<MemoryRouter><Header /></MemoryRouter>);

beforeEach(() => { vi.clearAllMocks(); cleanup(); });

describe('School name in the header', () => {
  it('shows the signed-in person\'s school', async () => {
    signedIn = { email: 'admin@us.test', full_name: 'US Admin' };
    current.mockResolvedValue(tenant('Maple Grove Academy'));
    show();
    expect(await screen.findByText('Maple Grove Academy')).toBeTruthy();
  });

  it('does not keep the first school\'s name when someone from another school signs in later in the same tab', async () => {
    signedIn = { email: 'masato@jp.test', full_name: 'Masato Yamano' };
    current.mockResolvedValue(tenant('みどり市立 若葉学園'));
    show();
    expect(await screen.findByText('みどり市立 若葉学園')).toBeTruthy();
    expect(screen.queryByText('Maple Grove Academy')).toBeNull();
    await waitFor(() => expect(current).toHaveBeenCalled());
  });

  it('the same person does not fetch it again when the header is shown again', async () => {
    signedIn = { email: 'masato@jp.test', full_name: 'Masato Yamano' };
    current.mockResolvedValue(tenant('みどり市立 若葉学園'));
    show();
    expect(await screen.findByText('みどり市立 若葉学園')).toBeTruthy();
    const calls = current.mock.calls.length;
    cleanup();
    show();
    expect(await screen.findByText('みどり市立 若葉学園')).toBeTruthy();
    expect(current.mock.calls.length).toBe(calls);
  });
});
