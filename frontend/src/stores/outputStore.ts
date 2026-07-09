import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface OutputItem {
  id: string
  title: string
  template: string
  content: string
  createdAt: number
}

interface OutputStore {
  outputs: OutputItem[]
  addOutput: (template: string, content: string) => void
  removeOutput: (id: string) => void
  clearAll: () => void
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

function extractTitle(content: string): string {
  // 取第一行有效标题（去掉 # 和首尾空白）
  const firstLine = content.trim().split('\n')[0] ?? ''
  return firstLine.replace(/^#+\s*/, '').trim().slice(0, 60) || '未命名笔记'
}

export const useOutputStore = create<OutputStore>()(
  persist(
    (set) => ({
      outputs: [],

      addOutput: (template, content) =>
        set((state) => ({
          outputs: [
            {
              id: generateId(),
              title: extractTitle(content),
              template,
              content,
              createdAt: Date.now(),
            },
            ...state.outputs,
          ].slice(0, 50), // 保留最近 50 条
        })),

      removeOutput: (id) =>
        set((state) => ({
          outputs: state.outputs.filter((o) => o.id !== id),
        })),

      clearAll: () => set({ outputs: [] }),
    }),
    {
      name: 'study-agent-outputs',
      version: 1,
    },
  ),
)
