// Which guided tours a person has finished or skipped.
import api from './api';

export type TourOutcome = 'completed' | 'skipped';
export type TourProgress = Record<string, { version: number; status: TourOutcome }>;

export const START_TOUR_EVENT = 'ccems:start-tour';

/** Ask the tour to open now (used by the "Take the tour" buttons). */
export const startTour = () => window.dispatchEvent(new Event(START_TOUR_EVENT));

/** True until this person has finished this version of the tour. Skipping does not count: it only hides the tour for the rest of
 *  that sign-in (see below), and the tour comes back at the next sign-in until every step has been seen. */
export const needsTour = (progress: TourProgress, tour: string, version: number): boolean => {
  const seen = progress[tour];
  return !seen || seen.version < version || seen.status !== 'completed';
};

const SKIPPED_KEY = 'ccems:tour-skipped';

/** Hide the tour for the rest of this sign-in. */
export const skipForThisSignIn = (tour: string) => { try { sessionStorage.setItem(SKIPPED_KEY, tour); } catch { /* private window */ } };
/** Whether the person skipped this tour since they last signed in. */
export const skippedThisSignIn = (tour: string): boolean => { try { return sessionStorage.getItem(SKIPPED_KEY) === tour; } catch { return false; } };
/** A new sign-in (or a sign-out) starts fresh, so a skipped tour is offered again. */
export const forgetSkip = () => { try { sessionStorage.removeItem(SKIPPED_KEY); } catch { /* ignore */ } };

const tourApi = {
  async progress(): Promise<TourProgress> { return (await api.get('/tour/progress/')).data.tours; },
  async record(tour: string, version: number, status: TourOutcome): Promise<TourProgress> {
    return (await api.post('/tour/progress/', { tour, version, status })).data.tours;
  },
};

export default tourApi;
