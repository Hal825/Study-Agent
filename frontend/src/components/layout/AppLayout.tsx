import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import OutputSidebar from './OutputSidebar'

export default function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto scrollbar-thin">
        <Outlet />
      </main>
      <OutputSidebar />
    </div>
  )
}
