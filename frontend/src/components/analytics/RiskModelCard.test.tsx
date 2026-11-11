// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

vi.mock('@/services/api', () => ({ default: { get: vi.fn() } }));

import api from '@/services/api';
import RiskModelCard from './RiskModelCard';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const card = (over = {}) => ({
  title: 'How the student risk scores are made',
  summary: 'The scores are advice for staff. They were not learned from recorded outcomes.',
  training_data: 'Fitted on your students plus generated rows.', levels: 'Cut-offs 25, 50 and 75.', missing_data: 'A typical value is assumed.',
  human_review: 'A person reviews each flag.',
  models: [{ name: 'Dropout risk', algorithm: 'XGBoost classifier', inputs: ['Attendance rate'], rule: 'Labelled at risk above 0.45.' }],
  not_used: ['Gender', 'Family income'], limits: ['No accuracy figures.'], available: true, latest_run: null, ...over,
});

beforeEach(() => { vi.clearAllMocks(); cleanup(); });

describe('Risk model card', () => {
  it('loads only when opened, and says what the scores are not', async () => {
    get.mockResolvedValue({ data: card() });
    render(<RiskModelCard />);
    expect(get).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText(/How these scores are made/));
    expect(await screen.findByText(/not learned from recorded outcomes/)).toBeTruthy();
    expect(screen.getByText(/Gender, Family income/)).toBeTruthy();
    expect(screen.getByText('No accuracy figures.')).toBeTruthy();
    expect(screen.getByText(/No scan has been run yet/)).toBeTruthy();
    expect(get).toHaveBeenCalledWith('/ai/risk-model-card/');
  });

  it('shows the latest scan, missing data and flag rates by group', async () => {
    get.mockResolvedValue({ data: card({ latest_run: {
      id: 'r1', ran_at: '2026-11-05T10:00:00Z', ran_by: 'Head', students_scored: 213,
      details: { training: { real_rows: 213, synthetic_rows: 200, model_version: 'v2' }, level_counts: { high: 105, low: 96 }, data_gaps: { 'no exam results (78% assumed)': 4 } },
      fairness: { gender: { groups: [{ group: 'female', students: 106, flagged: 49, flag_rate: 46.2 }, { group: 'male', students: 107, flagged: 56, flag_rate: 52.3 }], lowest_to_highest_rate: 0.88, hidden_small_groups: 0 },
                  class: { groups: [], lowest_to_highest_rate: null, hidden_small_groups: 0 } },
    } }) });
    render(<RiskModelCard />);
    fireEvent.click(screen.getByText(/How these scores are made/));
    expect(await screen.findByText(/213 students scored/)).toBeTruthy();
    expect(screen.getByText(/using 213 of your students and 200 generated rows/)).toBeTruthy();
    expect(screen.getByText(/4 with no exam results/)).toBeTruthy();
    expect(screen.getByText(/female: 49 of 106 flagged high or critical \(46.2%\)/)).toBeTruthy();
    expect(screen.getByText(/no group is large enough/)).toBeTruthy();
    expect(screen.getByText(/cannot show that the flags are fair/)).toBeTruthy();
  });

  it('shows the reason when it cannot load (for example AI is switched off)', async () => {
    get.mockRejectedValue({ response: { data: { error: 'AI is switched off for your school.' } } });
    render(<RiskModelCard />);
    fireEvent.click(screen.getByText(/How these scores are made/));
    expect(await screen.findByText('AI is switched off for your school.')).toBeTruthy();
  });
});
