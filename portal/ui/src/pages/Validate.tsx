import { useState } from 'react'
import { api } from '../api'

export default function ValidatePage() {
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
        setResult(await api.validateUpload(dslFile, sampleFile || undefined))
      } else {
        setResult(await api.validate(dslPath, samplePath || undefined))
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
          <SummaryCard result={result} />
          {result.type_warnings?.length > 0 && <TypeWarnings warnings={result.type_warnings} />}
          {result.coverage && <CoverageCard coverage={result.coverage} />}
          <ColumnsTable columns={result.columns} />
        </div>
      )}
    </div>
  )
}

function SummaryCard({ result }: { result: any }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h2 className="font-semibold mb-2">Compilation Summary</h2>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <dt className="text-gray-500">Transaction Type</dt><dd>{result.transaction_type}</dd>
        <dt className="text-gray-500">Compiled To</dt><dd className="truncate">{result.compiled_yaml_path}</dd>
        <dt className="text-gray-500">Columns</dt><dd>{result.columns?.length}</dd>
        <dt className="text-gray-500">Records</dt><dd>{Object.keys(result.records || {}).join(', ')}</dd>
      </dl>
    </div>
  )
}

function TypeWarnings({ warnings }: { warnings: any[] }) {
  return (
    <div className="bg-yellow-50 rounded-lg shadow p-4">
      <h2 className="font-semibold mb-2 text-yellow-800">Type Warnings ({warnings.length})</h2>
      <ul className="text-sm space-y-1">
        {warnings.map((tw, i) => (
          <li key={i}><span className="font-mono">{tw.field_name}</span> ({tw.record_name}): {tw.dsl_type} &rarr; {tw.compiled_type}</li>
        ))}
      </ul>
    </div>
  )
}

function CoverageCard({ coverage }: { coverage: any }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h2 className="font-semibold mb-2">Coverage</h2>
      <div className="text-sm">
        <div className="mb-2">
          <div className="flex justify-between"><span>Coverage</span><span className="font-bold">{coverage.coverage_pct.toFixed(1)}%</span></div>
          <div className="w-full bg-gray-200 rounded h-2 mt-1">
            <div className="bg-blue-600 rounded h-2" style={{ width: `${Math.min(100, coverage.coverage_pct)}%` }} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>Source: {coverage.source_fields_mapped}/{coverage.source_fields_total} mapped</div>
          <div>Target: {coverage.target_fields_populated}/{coverage.target_fields_total} populated</div>
        </div>
      </div>
    </div>
  )
}

function ColumnsTable({ columns }: { columns: any[] }) {
  if (!columns?.length) return null
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h2 className="font-semibold mb-2">Schema Columns</h2>
      <div className="overflow-auto max-h-96">
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-50"><tr><th className="px-2 py-1">Name</th><th className="px-2 py-1">Type</th><th className="px-2 py-1">DSL Type</th><th className="px-2 py-1">Record</th><th className="px-2 py-1">OK</th></tr></thead>
          <tbody>
            {columns.map((c: any, i: number) => (
              <tr key={i} className="border-t"><td className="px-2 py-1 font-mono">{c.name}</td><td className="px-2 py-1">{c.compiled_type}</td><td className="px-2 py-1">{c.dsl_type || '—'}</td><td className="px-2 py-1">{c.record_name}</td><td className="px-2 py-1">{c.type_preserved ? '✓' : '✗'}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
