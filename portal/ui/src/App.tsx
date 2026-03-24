import { useState, useEffect } from 'react'
import { api } from './api'

type Page = 'dashboard' | 'validate' | 'pipeline' | 'tests' | 'config'

const NAV: { key: Page; label: string }[] = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'validate', label: 'Validate' },
  { key: 'pipeline', label: 'Pipeline' },
  { key: 'tests', label: 'Tests' },
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
      {/* Sidebar */}
      <nav className="w-56 bg-gray-900 text-gray-200 flex flex-col">
        <div className="px-4 py-4 text-lg font-bold tracking-tight text-white">
          PyEDI Portal
        </div>
        <div className="flex-1">
          {NAV.map(n => (
            <button
              key={n.key}
              onClick={() => setPage(n.key)}
              className={`block w-full text-left px-4 py-2 text-sm hover:bg-gray-800 ${
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

      {/* Main content */}
      <main className="flex-1 overflow-auto p-6">
        {page === 'dashboard' && <DashboardPage />}
        {page === 'validate' && <ValidatePage />}
        {page === 'pipeline' && <PipelinePage />}
        {page === 'tests' && <TestsPage />}
        {page === 'config' && <ConfigPage />}
      </main>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Dashboard                                                          */
/* ------------------------------------------------------------------ */
function DashboardPage() {
  const [stats, setStats] = useState<any>(null)
  useEffect(() => { api.manifestStats().then(setStats).catch(() => {}) }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Dashboard</h1>
      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <StatCard label="Total" value={stats.total} />
          <StatCard label="Success" value={stats.success} color="text-green-600" />
          <StatCard label="Failed" value={stats.failed} color="text-red-600" />
          <StatCard label="Skipped" value={stats.skipped} color="text-yellow-600" />
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="text-sm text-gray-500">{label}</div>
      <div className={`text-3xl font-bold ${color || 'text-gray-900'}`}>{value}</div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Validate                                                           */
/* ------------------------------------------------------------------ */
function ValidatePage() {
  const [dslPath, setDslPath] = useState('')
  const [samplePath, setSamplePath] = useState('')
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [dslFile, setDslFile] = useState<File | null>(null)
  const [sampleFile, setSampleFile] = useState<File | null>(null)

  const runValidate = async () => {
    setError('')
    setResult(null)
    setLoading(true)
    try {
      if (dslFile) {
        const r = await api.validateUpload(dslFile, sampleFile || undefined)
        setResult(r)
      } else {
        const r = await api.validate(dslPath, samplePath || undefined)
        setResult(r)
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Schema Validation</h1>

      <div className="bg-white rounded-lg shadow p-4 mb-4 space-y-3">
        <h2 className="font-semibold text-sm text-gray-500 uppercase">By Path</h2>
        <div className="flex gap-2">
          <input className="border rounded px-3 py-1.5 flex-1 text-sm" placeholder="DSL file path" value={dslPath} onChange={e => setDslPath(e.target.value)} />
          <input className="border rounded px-3 py-1.5 flex-1 text-sm" placeholder="Sample file path (optional)" value={samplePath} onChange={e => setSamplePath(e.target.value)} />
        </div>

        <h2 className="font-semibold text-sm text-gray-500 uppercase pt-2">Or Upload</h2>
        <div className="flex gap-2">
          <input type="file" className="text-sm" onChange={e => setDslFile(e.target.files?.[0] || null)} />
          <input type="file" className="text-sm" onChange={e => setSampleFile(e.target.files?.[0] || null)} />
        </div>

        <button onClick={runValidate} disabled={loading || (!dslPath && !dslFile)} className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50">
          {loading ? 'Validating...' : 'Validate'}
        </button>
      </div>

      {error && <div className="bg-red-50 text-red-700 p-3 rounded mb-4 text-sm">{error}</div>}

      {result && (
        <div className="space-y-4">
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="font-semibold mb-2">Compilation Summary</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <dt className="text-gray-500">Transaction Type</dt><dd>{result.transaction_type}</dd>
              <dt className="text-gray-500">Compiled To</dt><dd className="truncate">{result.compiled_yaml_path}</dd>
              <dt className="text-gray-500">Columns</dt><dd>{result.columns?.length}</dd>
              <dt className="text-gray-500">Records</dt><dd>{Object.keys(result.records || {}).join(', ')}</dd>
            </dl>
          </div>

          {result.type_warnings?.length > 0 && (
            <div className="bg-yellow-50 rounded-lg shadow p-4">
              <h2 className="font-semibold mb-2 text-yellow-800">Type Warnings ({result.type_warnings.length})</h2>
              <ul className="text-sm space-y-1">
                {result.type_warnings.map((tw: any, i: number) => (
                  <li key={i}><span className="font-mono">{tw.field_name}</span> ({tw.record_name}): {tw.dsl_type} &rarr; {tw.compiled_type}</li>
                ))}
              </ul>
            </div>
          )}

          {result.coverage && (
            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="font-semibold mb-2">Coverage</h2>
              <div className="text-sm">
                <div className="mb-2">
                  <div className="flex justify-between"><span>Coverage</span><span className="font-bold">{result.coverage.coverage_pct.toFixed(1)}%</span></div>
                  <div className="w-full bg-gray-200 rounded h-2 mt-1">
                    <div className="bg-blue-600 rounded h-2" style={{ width: `${Math.min(100, result.coverage.coverage_pct)}%` }} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>Source: {result.coverage.source_fields_mapped}/{result.coverage.source_fields_total} mapped</div>
                  <div>Target: {result.coverage.target_fields_populated}/{result.coverage.target_fields_total} populated</div>
                </div>
              </div>
            </div>
          )}

          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="font-semibold mb-2">Schema Columns</h2>
            <div className="overflow-auto max-h-96">
              <table className="w-full text-sm text-left">
                <thead className="bg-gray-50"><tr><th className="px-2 py-1">Name</th><th className="px-2 py-1">Type</th><th className="px-2 py-1">DSL Type</th><th className="px-2 py-1">Record</th><th className="px-2 py-1">OK</th></tr></thead>
                <tbody>
                  {result.columns?.map((c: any, i: number) => (
                    <tr key={i} className="border-t"><td className="px-2 py-1 font-mono">{c.name}</td><td className="px-2 py-1">{c.compiled_type}</td><td className="px-2 py-1">{c.dsl_type || '—'}</td><td className="px-2 py-1">{c.record_name}</td><td className="px-2 py-1">{c.type_preserved ? '✓' : '✗'}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Pipeline                                                           */
/* ------------------------------------------------------------------ */
function PipelinePage() {
  const [results, setResults] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  useEffect(() => { api.pipelineResults().then(setResults).catch(() => {}).finally(() => setLoading(false)) }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Pipeline Results</h1>
      {loading ? <p className="text-sm text-gray-500">Loading...</p> : results.length === 0 ? <p className="text-sm text-gray-500">No results yet.</p> : (
        <div className="bg-white rounded-lg shadow overflow-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-gray-50"><tr><th className="px-3 py-2">File</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Modified</th></tr></thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={i} className="border-t"><td className="px-3 py-2 font-mono text-xs">{r.filename}</td><td className="px-3 py-2"><StatusBadge status={r.status} /></td><td className="px-3 py-2 text-xs">{new Date(r.modified * 1000).toLocaleString()}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const cls = status === 'SUCCESS' ? 'bg-green-100 text-green-800' : status === 'FAILED' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{status}</span>
}

/* ------------------------------------------------------------------ */
/* Tests                                                              */
/* ------------------------------------------------------------------ */
function TestsPage() {
  const [cases, setCases] = useState<any[]>([])
  const [runResult, setRunResult] = useState<any>(null)
  const [running, setRunning] = useState(false)

  useEffect(() => { api.testCases().then(setCases).catch(() => {}) }, [])

  const runTests = async () => {
    setRunning(true)
    try { setRunResult(await api.testRun()) } catch {} finally { setRunning(false) }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Test Harness</h1>
        <button onClick={runTests} disabled={running} className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50">
          {running ? 'Running...' : 'Run Tests'}
        </button>
      </div>

      {runResult && (
        <div className="bg-white rounded-lg shadow p-4 mb-4">
          <div className="grid grid-cols-4 gap-4 text-center text-sm">
            <div><div className="text-gray-500">Total</div><div className="text-xl font-bold">{runResult.total}</div></div>
            <div><div className="text-gray-500">Passed</div><div className="text-xl font-bold text-green-600">{runResult.passed}</div></div>
            <div><div className="text-gray-500">Failed</div><div className="text-xl font-bold text-red-600">{runResult.failed}</div></div>
            <div><div className="text-gray-500">Warned</div><div className="text-xl font-bold text-yellow-600">{runResult.warned}</div></div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg shadow">
        <div className="px-4 py-2 bg-gray-50 font-semibold text-sm">Test Cases ({cases.length})</div>
        {cases.map((c, i) => (
          <div key={i} className="px-4 py-2 border-t text-sm">
            <div className="font-medium">{c.name}</div>
            <div className="text-xs text-gray-500">{c.input_file}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Config                                                             */
/* ------------------------------------------------------------------ */
function ConfigPage() {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => { api.config().then(setConfig).catch(() => {}).finally(() => setLoading(false)) }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Configuration</h1>
      {loading ? <p className="text-sm text-gray-500">Loading...</p> : config && (
        <div className="bg-white rounded-lg shadow p-4">
          <pre className="text-xs overflow-auto max-h-[70vh] whitespace-pre-wrap">{JSON.stringify(config, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

export default App
