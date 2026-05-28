import { create } from "zustand";

interface AppState {
  currentStyle: "formal" | "funny" | "tactical";
  setStyle: (style: "formal" | "funny" | "tactical") => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentStyle: "funny",
  setStyle: (style) => set({ currentStyle: style }),
}));
