// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
const push = vi.hoisted(() => ({
  state: vi.fn(), enable: vi.fn(), disable: vi.fn(), devices: vi.fn(), removeDevice: vi.fn(), types: vi.fn(), saveMuted: vi.fn(), sendTest: vi.fn(),
}));
vi.mock('@/services/push.service', () => ({ default: push }));
vi.mock('@/utils/pwa', () => ({ canInstall: () => false, isInstalled: () => false, isIos: () => false, onInstallChange: () => () => undefined, promptInstall: vi.fn() }));

import AppAndNotifications from './AppAndNotifications';

const types = [
  { key: 'attendance', label: 'Attendance', enabled: true }, { key: 'finance', label: 'Finance', enabled: true },
  { key: 'announcement', label: 'Announcement', enabled: false },
];

beforeEach(() => {
  vi.clearAllMocks(); cleanup();
  push.state.mockResolvedValue('off'); push.devices.mockResolvedValue([]); push.types.mockResolvedValue(types);
  push.enable.mockResolvedValue(undefined); push.disable.mockResolvedValue(undefined); push.saveMuted.mockResolvedValue(types); push.sendTest.mockResolvedValue(1); push.removeDevice.mockResolvedValue(undefined);
});

describe('push settings', () => {
  it('turns notifications on for this device', async () => {
    render(<AppAndNotifications />);
    fireEvent.click(await screen.findByRole('button', { name: 'Turn on' }));
    await waitFor(() => expect(push.enable).toHaveBeenCalled());
  });

  it('turns them off again when already on, and can send a test', async () => {
    push.state.mockResolvedValue('on');
    render(<AppAndNotifications />);
    fireEvent.click(await screen.findByRole('button', { name: 'Send a test' }));
    await waitFor(() => expect(push.sendTest).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Turn off' }));
    await waitFor(() => expect(push.disable).toHaveBeenCalled());
  });

  it('switching a kind off sends the full list of switched-off kinds', async () => {
    render(<AppAndNotifications />);
    fireEvent.click(await screen.findByLabelText('Finance'));
    await waitFor(() => expect(push.saveMuted).toHaveBeenCalledWith(['announcement', 'finance']));
  });

  it('explains each situation instead of showing a broken switch', async () => {
    for (const [state, text] of [['unsupported', /cannot receive push/], ['unavailable', /not switched on for this school/], ['blocked', /blocked for this site/]] as const) {
      cleanup(); push.state.mockResolvedValue(state);
      render(<AppAndNotifications />);
      expect(await screen.findByText(text)).toBeTruthy();
      expect(screen.queryByRole('button', { name: 'Turn on' })).toBeNull();
    }
  });

  it('lists devices and lets a person remove one', async () => {
    push.state.mockResolvedValue('on');
    push.devices.mockResolvedValue([{ id: 'd1', platform: 'android', user_agent: '', added: '2026-10-01T10:00:00Z', last_active: '2026-10-01T10:00:00Z' }]);
    render(<AppAndNotifications />);
    fireEvent.click(await screen.findByLabelText('Remove android device'));
    await waitFor(() => expect(push.removeDevice).toHaveBeenCalledWith('d1'));
  });
});
