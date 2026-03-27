import { useState, useEffect } from 'react'
import { api } from './api'
import DashboardPage from './pages/Dashboard'
import ValidatePage from './pages/Validate'
import PipelinePage from './pages/Pipeline'
import TestsPage from './pages/Tests'
import ConfigPage from './pages/Config'
import ComparePage from './pages/Compare'
import OnboardPage from './pages/Onboard'
import RulesPage from './pages/Rules'

type Page = 'dashboard' | 'validate' | 'pipeline' | 'tests' | 'compare' | 'rules' | 'config' | 'onboard'

const NAV: { key: Page; label: string }[] = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'validate', label: 'Validate' },
  { key: 'pipeline', label: 'Pipeline' },
  { key: 'tests', label: 'Tests' },
  { key: 'compare', label: 'Compare' },
  { key: 'rules', label: 'Rules' },
  { key: 'onboard', label: 'Onboard' },
  { key: 'config', label: 'Config' },
]

function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [health, setHealth] = useState<string>('...')

  useEffect(() => {
    api.health().then(d => setHealth(d.status)).catch(() => setHealth('offline'))
  }, [])

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      <nav className="w-56 bg-gray-900 text-gray-200 flex flex-col">
        <div className="px-4 py-4 text-lg font-bold tracking-tight text-white">
          PyEDI Portal
        </div>
        <div className="flex-1">
          {NAV.map(n => (
            <button
              key={n.key}
              onClick={() => setPage(n.key)}
              className={`block w-full text-left px-4 py-2 text-sm cursor-pointer hover:bg-gray-800 hover:text-white transition-colors ${
                page === n.key ? 'bg-gray-800 text-white font-medium' : ''
              }`}
            >
              {n.label}
            </button>
          ))}
        </div>
        <div className="px-4 py-3 text-xs text-gray-500">
          API: <span className={health === 'ok' ? 'text-green-400' : 'text-red-400'}>{health}</span>
        </div>
      </nav>

      <main className="flex-1 overflow-auto p-6">
        {page === 'dashboard' && <DashboardPage onNavigate={(p) => setPage(p as Page)} />}
        {page === 'validate' && <ValidatePage />}
        {page === 'pipeline' && <PipelinePage />}
        {page === 'tests' && <TestsPage />}
        {page === 'compare' && <ComparePage onNavigate={(p) => setPage(p as Page)} />}
        {page === 'rules' && <RulesPage onNavigate={(p) => setPage(p as Page)} />}
        {page === 'onboard' && <OnboardPage onNavigate={(p) => setPage(p as Page)} />}
        {page === 'config' && <ConfigPage />}
      </main>
    </div>
  )
}

export default App
