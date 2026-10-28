// Starred pages. They show in the top menu's Favourites panel. At most MAX_FAVOURITES, kept per computer.
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const MAX_FAVOURITES = 8;

export interface Favourite { href: string; label: string }

interface FavouritesState {
  items: Favourite[];
  /** Star or unstar a page. Returns false (and changes nothing) when the list is full. */
  toggle: (fav: Favourite) => boolean;
  has: (href: string) => boolean;
}

export const useFavourites = create<FavouritesState>()(
  persist(
    (set, get) => ({
      items: [],
      toggle: (fav) => {
        const { items } = get();
        if (items.some((f) => f.href === fav.href)) {
          set({ items: items.filter((f) => f.href !== fav.href) });
          return true;
        }
        if (items.length >= MAX_FAVOURITES) return false;
        set({ items: [...items, fav] });
        return true;
      },
      has: (href) => get().items.some((f) => f.href === href),
    }),
    { name: 'favourites-storage' },
  ),
);

export const FAVOURITES_FULL_MESSAGE = `Your favourites are full (${MAX_FAVOURITES}). Click a starred page to remove it first.`;
