import { useState, useEffect } from 'react'
import { api } from '../api'

export default function TestsPage() {
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

          {runResult.cases?.length > 0 && (
            <div className="mt-4 border-t pt-2">
              {runResult.cases.map((c: any, i: number) => (
                <div key={i} className="flex items-center gap-2 py-1 text-sm">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                    c.status === 'PASS' ? 'bg-green-100 text-green-800' :
                    c.status === 'FAIL' ? 'bg-red-100 text-red-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>{c.status}</span>
                  <span>{c.name}</span>
                  {c.details && <span className="text-gray-400 text-xs">({c.details})</span>}
                </div>
              ))}
            </div>
          )}
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
