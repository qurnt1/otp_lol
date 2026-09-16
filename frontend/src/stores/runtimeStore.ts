import { create } from "zustand";

import type { RuntimeSnapshot } from "../types/api";

export interface RuntimeStatus {
  message: string;
  level: string;
  timestamp: string;
}

interface RuntimeStore {
  runtime: RuntimeSnapshot | null;
  setRuntime: (runtime: RuntimeSnapshot) => void;
  status: RuntimeStatus;
  setStatus: (status: RuntimeStatus) => void;
}

export const useRuntimeStore = create<RuntimeStore>((set) => ({
  runtime: null,
  setRuntime: (runtime) => set({ runtime }),
  status: { message: "En attente de League pour synchroniser.", level: "INFO", timestamp: "" },
  setStatus: (status) => set({ status }),
}));
