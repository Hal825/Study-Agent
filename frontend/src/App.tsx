import { Routes, Route } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import Dashboard from './pages/Dashboard'
import NoteTool from './pages/tools/NoteTool'

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/tool/note" element={<NoteTool />} />
      </Route>
    </Routes>
  )
}

export default App
