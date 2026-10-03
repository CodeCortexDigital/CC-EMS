// Which guided tours a person has finished or skipped.
import api from './api';

export type TourOutcome = 'completed' | 'skipped';
export type TourProgress = Record<string, { version: number; status: TourOutcome }>;

export const START_TOUR_EVENT = 'ccems:start-tour';

/** Ask the tour to open now (used by the "Take the tour" buttons). */
export const startTour = () => window.dispatchEvent(new Event(START_TOUR_EVENT));

/** True when this person has not yet seen this version of the tour. */
export const needsTour = (progress: TourProgress, tour: string, version: number): boolean => {
  const seen = progress[tour];
  return !seen || seen.version < version;
};

const tourApi = {
  async progress(): Promise<TourProgress> { return (await api.get('/tour/progress/')).data.tours; },
  async record(tour: string, version: number, status: TourOutcome): Promise<TourProgress> {
    return (await api.post('/tour/progress/', { tour, version, status })).data.tours;
  },
};

export default tourApi;
