import { useState, useEffect } from 'react'
import { api } from '../api'

function StatusBadge({ status }: { status: string }) {
  const cls = status === 'SUCCESS' ? 'bg-green-100 text-green-800' : status === 'FAILED' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{status}</span>
}

export default function PipelinePage() {
  const [results, setResults] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.pipelineResults().then(setResults).catch(() => {}).finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Pipeline Results</h1>
      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : results.length === 0 ? (
        <p className="text-sm text-gray-500">No results yet.</p>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-gray-50">
              <tr><th className="px-3 py-2">File</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Modified</th></tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={i} className="border-t">
                  <td className="px-3 py-2 font-mono text-xs">{r.filename}</td>
                  <td className="px-3 py-2"><StatusBadge status={r.status} /></td>
                  <td className="px-3 py-2 text-xs">{new Date(r.modified * 1000).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
