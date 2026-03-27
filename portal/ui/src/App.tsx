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
      <nav className="w-56 bg-white border-r border-gray-200 text-gray-600 flex flex-col">
        <div className="px-4 py-4 text-lg font-bold tracking-tight text-gray-900">
          PyEDI Portal
        </div>
        <div className="flex-1">
          {NAV.map(n => (
            <button
              key={n.key}
              onClick={() => setPage(n.key)}
              className={`block w-full text-left px-4 py-2 text-sm cursor-pointer transition-colors ${
                page === n.key
                  ? 'bg-blue-50 text-blue-700 font-medium border-l-[3px] border-blue-500'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              }`}
            >
              {n.label}
            </button>
          ))}
        </div>
        <div className="px-4 py-3 text-xs text-gray-400">
          API: <span className={health === 'ok' ? 'text-green-500' : 'text-red-500'}>{health}</span>
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
