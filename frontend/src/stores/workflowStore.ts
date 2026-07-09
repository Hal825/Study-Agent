import { create } from 'zustand'
import type { WorkflowState, WorkflowStep } from '../types'

interface WorkflowActions {
  setStep: (step: WorkflowStep) => void
  setContent: (content: string) => void
  setSelectedTemplate: (templateId: string | null) => void
  setResult: (result: string) => void
  reset: () => void
}

const initialState: WorkflowState = {
  step: 'input',
  content: '',
  selectedTemplate: null,
  result: '',
}

export const useWorkflowStore = create<WorkflowState & WorkflowActions>((set) => ({
  ...initialState,

  setStep: (step) => set({ step }),

  setContent: (content) => set({ content }),

  setSelectedTemplate: (templateId) => set({ selectedTemplate: templateId }),

  setResult: (result) => set({ result }),

  reset: () => set(initialState),
}))
