import { useState, useEffect } from 'react'
import { api } from '../api'

export default function ConfigPage() {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.config().then(setConfig).catch(() => {}).finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Configuration</h1>
      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : config && (
        <div className="bg-white rounded-lg shadow p-4">
          <pre className="text-xs overflow-auto max-h-[70vh] whitespace-pre-wrap">
            {JSON.stringify(config, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
