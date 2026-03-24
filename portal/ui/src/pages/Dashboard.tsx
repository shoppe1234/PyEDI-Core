import { useState, useEffect } from 'react'
import { api } from '../api'

function StatCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="text-sm text-gray-500">{label}</div>
      <div className={`text-3xl font-bold ${color || 'text-gray-900'}`}>{value}</div>
    </div>
  )
}

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null)
  const [recent, setRecent] = useState<any[]>([])

  useEffect(() => {
    api.manifestStats().then(setStats).catch(() => {})
    api.manifestEntries(10).then(setRecent).catch(() => {})
  }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Dashboard</h1>

      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatCard label="Total Processed" value={stats.total} />
          <StatCard label="Success" value={stats.success} color="text-green-600" />
          <StatCard label="Failed" value={stats.failed} color="text-red-600" />
          <StatCard label="Skipped" value={stats.skipped} color="text-yellow-600" />
        </div>
      )}

      {recent.length > 0 && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-4 py-2 bg-gray-50 font-semibold text-sm">Recent Processing</div>
          {recent.map((e, i) => (
            <div key={i} className="px-4 py-2 border-t text-sm flex justify-between">
              <span className="font-mono text-xs">{e.filename}</span>
              <span className={`text-xs font-medium ${e.status === 'SUCCESS' ? 'text-green-600' : 'text-red-600'}`}>{e.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
