import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UIState {
  navCollapsed: boolean;
  sourcePanelOpen: boolean;
  activeSourceTab: "tree" | "citations" | "metadata";
  commandPaletteOpen: boolean;
  toggleNav: () => void;
  setNavCollapsed: (v: boolean) => void;
  toggleSourcePanel: () => void;
  setSourcePanelOpen: (v: boolean) => void;
  setActiveSourceTab: (tab: "tree" | "citations" | "metadata") => void;
  setCommandPaletteOpen: (v: boolean) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      navCollapsed: false,
      sourcePanelOpen: true,
      activeSourceTab: "citations",
      commandPaletteOpen: false,
      toggleNav: () => set((s) => ({ navCollapsed: !s.navCollapsed })),
      setNavCollapsed: (v) => set({ navCollapsed: v }),
      toggleSourcePanel: () =>
        set((s) => ({ sourcePanelOpen: !s.sourcePanelOpen })),
      setSourcePanelOpen: (v) => set({ sourcePanelOpen: v }),
      setActiveSourceTab: (tab) => set({ activeSourceTab: tab }),
      setCommandPaletteOpen: (v) => set({ commandPaletteOpen: v }),
    }),
    {
      name: "findoc-ui",
      partialize: (s) => ({
        navCollapsed: s.navCollapsed,
        sourcePanelOpen: s.sourcePanelOpen,
        activeSourceTab: s.activeSourceTab,
      }),
    }
  )
);
