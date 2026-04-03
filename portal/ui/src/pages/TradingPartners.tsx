import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import { emitProfileChanged, useProfileChanged } from '../profileEvents'

interface Profile {
  name: string
  trading_partner: string
  transaction_type: string
  description: string
  rules_file: string
}

export default function TradingPartners({ onNavigate }: { onNavigate?: (page: string) => void }) {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deleting, setDeleting] = useState<string | null>(null)

  const loadProfiles = useCallback(() => {
    setLoading(true)
    api.compareProfiles()
      .then((data: Profile[]) => { setProfiles(data); setError('') })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadProfiles() }, [loadProfiles])

  useProfileChanged(useCallback(() => loadProfiles(), [loadProfiles]))

  const handleDelete = async (name: string) => {
    if (!window.confirm(`Delete profile "${name}"? This removes the profile config and its rules file. Compare history is preserved.`)) {
      return
    }
    setDeleting(name)
    try {
      await api.profileDelete(name)
      emitProfileChanged({ action: 'deleted', profileName: name })
      setProfiles(prev => prev.filter(p => p.name !== name))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setDeleting(null)
    }
  }

  const filtered = profiles.filter(p => {
    if (!search) return true
    const q = search.toLowerCase()
    return p.name.toLowerCase().includes(q)
      || p.trading_partner?.toLowerCase().includes(q)
      || p.transaction_type?.toLowerCase().includes(q)
  })

  const formatBadge = (txnType: string) => {
    const t = txnType?.toLowerCase() || ''
    if (/^\d{3}/.test(t)) return { label: 'X12', color: 'bg-indigo-100 text-indigo-700' }
    if (t.includes('csv') || t.includes('flat')) return { label: 'CSV', color: 'bg-emerald-100 text-emerald-700' }
    if (t.includes('xml') || t.includes('cxml')) return { label: 'XML', color: 'bg-amber-100 text-amber-700' }
    return { label: txnType || '?', color: 'bg-gray-100 text-gray-600' }
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Trading Partners</h1>
          <p className="text-sm text-gray-500 mt-1">
            {profiles.length} profile{profiles.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        {onNavigate && (
          <button
            onClick={() => onNavigate('onboard')}
            className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium
                       hover:bg-indigo-700 transition-colors shadow-sm"
          >
            Onboard New Partner
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        {/* Search */}
        <div className="mb-4">
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, partner, or type..."
            className="w-full max-w-sm border border-gray-200 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
          />
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12 text-gray-400 gap-2">
            <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading profiles...
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-gray-400 text-sm">
            {search ? 'No profiles match your search.' : 'No profiles configured yet.'}
          </div>
        ) : (
          <div className="overflow-auto">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-xs uppercase text-gray-500 tracking-wider font-medium px-3 py-2">Name</th>
                  <th className="text-xs uppercase text-gray-500 tracking-wider font-medium px-3 py-2">Trading Partner</th>
                  <th className="text-xs uppercase text-gray-500 tracking-wider font-medium px-3 py-2">Type</th>
                  <th className="text-xs uppercase text-gray-500 tracking-wider font-medium px-3 py-2">Description</th>
                  <th className="text-xs uppercase text-gray-500 tracking-wider font-medium px-3 py-2">Rules File</th>
                  <th className="text-xs uppercase text-gray-500 tracking-wider font-medium px-3 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p, i) => {
                  const badge = formatBadge(p.transaction_type)
                  return (
                    <tr key={p.name} className={`border-b border-gray-50 hover:bg-gray-50/50 ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50/30'}`}>
                      <td className="px-3 py-2.5 font-bold text-gray-900">{p.name}</td>
                      <td className="px-3 py-2.5 text-gray-500">{p.trading_partner || <span className="text-gray-300">--</span>}</td>
                      <td className="px-3 py-2.5">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badge.color}`}>
                          {badge.label}
                        </span>
                        <span className="ml-1.5 text-gray-500 text-xs">{p.transaction_type}</span>
                      </td>
                      <td className="px-3 py-2.5 text-gray-500 max-w-xs truncate">{p.description || '--'}</td>
                      <td className="px-3 py-2.5">
                        <span className="font-mono text-xs text-gray-400">{p.rules_file}</span>
                      </td>
                      <td className="px-3 py-2.5 text-right whitespace-nowrap">
                        {onNavigate && (
                          <button
                            onClick={() => onNavigate('rules')}
                            className="text-indigo-600 hover:text-indigo-800 text-sm mr-3"
                          >
                            View Rules
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(p.name)}
                          disabled={deleting === p.name}
                          className="text-red-600 hover:text-red-800 text-sm disabled:opacity-40"
                        >
                          {deleting === p.name ? 'Deleting...' : 'Delete'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
