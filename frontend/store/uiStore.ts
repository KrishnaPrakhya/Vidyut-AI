import { create } from "zustand";

interface UIState {
  sidebarOpen: boolean;
  activeRoute: string;
  theme: "light" | "dark";
  toggleSidebar: () => void;
  setActiveRoute: (route: string) => void;
  setTheme: (theme: "light" | "dark") => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  activeRoute: "/",
  theme: "light",
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setActiveRoute: (activeRoute) => set({ activeRoute }),
  setTheme: (theme) => set({ theme }),
}));
