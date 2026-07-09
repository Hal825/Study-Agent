import { create } from 'zustand'
import type { AgentState } from '../types'

interface AgentActions {
  startProcessing: () => void
  advanceStage: () => void
  finishProcessing: () => void
  setError: (error: string | null) => void
}

const initialState: AgentState = {
  isProcessing: false,
  currentStageIndex: 0,
  error: null,
}

export const useAgentStore = create<AgentState & AgentActions>((set, get) => ({
  ...initialState,

  startProcessing: () =>
    set({ isProcessing: true, currentStageIndex: 0, error: null }),

  advanceStage: () => {
    const { currentStageIndex } = get()
    set({ currentStageIndex: currentStageIndex + 1 })
  },

  finishProcessing: () =>
    set({ isProcessing: false, currentStageIndex: 0 }),

  setError: (error) => set({ error, isProcessing: false }),
}))
