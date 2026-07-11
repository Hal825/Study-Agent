import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { PanelRightOpen, PanelRightClose } from 'lucide-react'
import Sidebar from './Sidebar'
import OutputSidebar from './OutputSidebar'

export default function AppLayout() {
  const [outputOpen, setOutputOpen] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden bg-paper">
      <Sidebar />

      <main className="flex-1 overflow-y-auto scrollbar-thin">
        <Outlet />
      </main>

      {/* Toggle button column */}
      <div className="flex flex-col items-center border-l border-border bg-surface py-3 w-10">
        <button
          onClick={() => setOutputOpen(!outputOpen)}
          className={`rounded-lg p-1.5 transition-all ${
            outputOpen
              ? 'text-primary-600 bg-primary-50'
              : 'text-ink-muted/40 hover:text-ink-soft hover:bg-paper-dark'
          }`}
          title={outputOpen ? '收起输出历史' : '展开输出历史'}
        >
          {outputOpen ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
        </button>
      </div>

      {outputOpen && <OutputSidebar onClose={() => setOutputOpen(false)} />}
    </div>
  )
}
