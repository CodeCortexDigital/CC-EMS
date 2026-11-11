import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/** Where the main menu sits: down the side (the default) or along the top for staff roles. Remembered per computer. */
export type NavLayout = 'top' | 'side';
/** The side menu: pinned open, pinned collapsed, or free (opens when the pointer is on it). */
export type SidebarLock = 'open' | 'closed' | 'none';

interface UIState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  navLayout: NavLayout;
  setNavLayout: (layout: NavLayout) => void;
  sidebarLock: SidebarLock;
  setSidebarLock: (lock: SidebarLock) => void;
  theme: {
    sidebarBg: string;
    activeColor: string;
  };
  setTheme: (theme: { sidebarBg: string; activeColor: string }) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set((state) => ({
        sidebarCollapsed: !state.sidebarCollapsed
      })),
      setSidebarCollapsed: (collapsed) => set({
        sidebarCollapsed: collapsed
      }),
      navLayout: 'side',
      setNavLayout: (navLayout) => set({ navLayout }),
      sidebarLock: 'none',
      setSidebarLock: (sidebarLock) => set({ sidebarLock }),
      theme: {
        sidebarBg: 'Dark',
        activeColor: 'Soft Light Purple'
      },
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: 'ui-storage',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        navLayout: state.navLayout,
        sidebarLock: state.sidebarLock,
        theme: state.theme,
      }),
    }
  )
);
