// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

const region = vi.hoisted(() => ({ value: 'us' }));
vi.mock('@/utils/region', () => ({ useRegion: () => ({ region: region.value }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({ API_BASE_URL: 'http://x/api/v1', default: { get: vi.fn(), post: vi.fn() } }));
const gateways = vi.hoisted(() => vi.fn());
vi.mock('@/services/billing.service', () => ({ default: { gateways, saveGateway: vi.fn(), deleteGateway: vi.fn() } }));

import OnlinePaymentsPage from './OnlinePaymentsPage';

beforeEach(() => { vi.clearAllMocks(); cleanup(); gateways.mockResolvedValue([]); });

describe('Online payment providers', () => {
  it('offers only Stripe to a US school', async () => {
    region.value = 'us';
    render(<OnlinePaymentsPage />);
    expect(await screen.findByText('Stripe')).toBeTruthy();
    expect(screen.queryByText('JazzCash')).toBeNull();
    expect(screen.queryByText('Easypaisa')).toBeNull();
  });

  it('offers the Pakistani wallets to a school set to the Pakistan region', async () => {
    region.value = 'pk';
    render(<OnlinePaymentsPage />);
    expect(await screen.findByText('JazzCash')).toBeTruthy();
    expect(screen.getByText('Easypaisa')).toBeTruthy();
  });

  it('keeps a wallet that a school has already set up, whatever its region', async () => {
    region.value = 'us';
    gateways.mockResolvedValue([{ id: 'g1', provider: 'jazzcash', provider_display: 'JazzCash', name: 'JazzCash', merchant_id: 'm', api_url: '', callback_url: '', is_active: true, has_api_key: true }]);
    render(<OnlinePaymentsPage />);
    expect(await screen.findByText('JazzCash')).toBeTruthy();
    expect(screen.queryByText('Easypaisa')).toBeNull();
  });
});
