import { useState, useEffect } from 'react'
import { api } from '../api'

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    MATCH: 'bg-green-100 text-green-800',
    MISMATCH: 'bg-red-100 text-red-800',
    UNMATCHED: 'bg-yellow-100 text-yellow-800',
    hard: 'bg-red-100 text-red-800',
    soft: 'bg-yellow-100 text-yellow-800',
    ignore: 'bg-gray-100 text-gray-600',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  )
}

export default function ComparePage() {
  // Profiles
  const [profiles, setProfiles] = useState<any[]>([])
  const [selectedProfile, setSelectedProfile] = useState('')
  const [profileDetail, setProfileDetail] = useState<any>(null)

  // New comparison form
  const [sourceDir, setSourceDir] = useState('')
  const [targetDir, setTargetDir] = useState('')
  const [running, setRunning] = useState(false)

  // Run history
  const [runs, setRuns] = useState<any[]>([])
  const [selectedRun, setSelectedRun] = useState<any>(null)
  const [pairs, setPairs] = useState<any[]>([])
  const [statusFilter, setStatusFilter] = useState('')

  // Pair detail
  const [selectedPair, setSelectedPair] = useState<any>(null)
  const [diffs, setDiffs] = useState<any[]>([])

  // Rules editor
  const [showRules, setShowRules] = useState(false)
  const [rulesJson, setRulesJson] = useState('')
  const [rulesSaving, setRulesSaving] = useState(false)

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Tab view
  const [view, setView] = useState<'runs' | 'discoveries'>('runs')

  // Reclassify
  const [reclassifying, setReclassifying] = useState(false)

  // Summary
  const [summary, setSummary] = useState<any>(null)

  // Run diff
  const [checkedRuns, setCheckedRuns] = useState<Set<number>>(new Set())
  const [runDiff, setRunDiff] = useState<any>(null)
  const [diffLoading, setDiffLoading] = useState(false)

  // Discoveries
  const [discoveries, setDiscoveries] = useState<any[]>([])
  const [discoveryFilter, setDiscoveryFilter] = useState<string>('all')
  const [discoveryLoading, setDiscoveryLoading] = useState(false)
  const [applyingId, setApplyingId] = useState<number | null>(null)

  // Load profiles on mount
  useEffect(() => {
    api.compareProfiles().then(setProfiles).catch(e => setError(e.message))
    loadRuns()
  }, [])

  // Update profile detail when selection changes
  useEffect(() => {
    const p = profiles.find(p => p.name === selectedProfile)
    setProfileDetail(p || null)
  }, [selectedProfile, profiles])

  const loadRuns = () => {
    api.compareRuns().then(setRuns).catch(e => setError(e.message))
  }

  const runComparison = async () => {
    setError('')
    setRunning(true)
    try {
      await api.compareRun(selectedProfile, sourceDir, targetDir)
      loadRuns()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  const selectRun = async (run: any) => {
    setSelectedRun(run)
    setSelectedPair(null)
    setDiffs([])
    setStatusFilter('')
    setSummary(null)
    setLoading(true)
    try {
      setPairs(await api.comparePairs(run.run_id))
      setSummary(await api.compareRunSummary(run.run_id))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const filterPairs = async (status: string) => {
    setStatusFilter(status)
    if (!selectedRun) return
    setLoading(true)
    try {
      setPairs(await api.comparePairs(selectedRun.run_id, status || undefined))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const selectPair = async (pair: any) => {
    setSelectedPair(pair)
    setLoading(true)
    try {
      setDiffs(await api.compareDiffs(pair.run_id, pair.id))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const loadRules = async () => {
    if (!selectedProfile) return
    setShowRules(true)
    try {
      const rules = await api.compareRules(selectedProfile)
      setRulesJson(JSON.stringify(rules, null, 2))
    } catch (e: any) {
      setError(e.message)
    }
  }

  const saveRules = async () => {
    if (!selectedProfile) return
    setRulesSaving(true)
    try {
      const parsed = JSON.parse(rulesJson)
      await api.compareUpdateRules(selectedProfile, parsed)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setRulesSaving(false)
    }
  }

  const reclassifyRun = async () => {
    if (!selectedRun) return
    setReclassifying(true)
    setError('')
    try {
      await api.compareReclassify(selectedRun.run_id)
      loadRuns()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setReclassifying(false)
    }
  }

  const toggleRunCheck = (runId: number) => {
    setCheckedRuns(prev => {
      const next = new Set(prev)
      if (next.has(runId)) {
        next.delete(runId)
      } else if (next.size < 2) {
        next.add(runId)
      }
      return next
    })
    setRunDiff(null)
  }

  const diffSelectedRuns = async () => {
    const ids = Array.from(checkedRuns).sort((a, b) => a - b)
    if (ids.length !== 2) return
    setDiffLoading(true)
    setError('')
    try {
      setRunDiff(await api.compareRunDiff(ids[0], ids[1]))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setDiffLoading(false)
    }
  }

  const loadDiscoveries = async () => {
    if (!selectedProfile) return
    setDiscoveryLoading(true)
    try {
      const applied = discoveryFilter === 'all' ? undefined : discoveryFilter === 'applied'
      setDiscoveries(await api.compareDiscoveries(selectedProfile, applied))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setDiscoveryLoading(false)
    }
  }

  const applyDiscovery = async (id: number) => {
    setApplyingId(id)
    setError('')
    try {
      await api.compareApplyDiscovery(id)
      loadDiscoveries()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setApplyingId(null)
    }
  }

  useEffect(() => {
    if (view === 'discoveries' && selectedProfile) {
      loadDiscoveries()
    }
  }, [view, selectedProfile, discoveryFilter])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Compare</h1>

      <div className="flex gap-1 mb-4">
        {(['runs', 'discoveries'] as const).map(v => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`px-3 py-1 rounded text-sm capitalize ${view === v ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
          >
            {v}
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded mb-4 text-sm">
          {error}
          <button onClick={() => setError('')} className="ml-2 text-red-500 hover:text-red-700">&times;</button>
        </div>
      )}

      {view === 'runs' && (
      <>
      {/* New Comparison */}
      <div className="bg-white rounded-lg shadow p-4 mb-4 space-y-3">
        <h2 className="font-semibold text-sm text-gray-500 uppercase">New Comparison</h2>
        <div className="flex gap-2 items-end">
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">Profile</label>
            <select
              className="border rounded px-3 py-1.5 w-full text-sm"
              value={selectedProfile}
              onChange={e => setSelectedProfile(e.target.value)}
            >
              <option value="">Select profile...</option>
              {profiles.map(p => (
                <option key={p.name} value={p.name}>{p.name}</option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">Source Directory</label>
            <input className="border rounded px-3 py-1.5 w-full text-sm" placeholder="/path/to/source" value={sourceDir} onChange={e => setSourceDir(e.target.value)} />
          </div>
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">Target Directory</label>
            <input className="border rounded px-3 py-1.5 w-full text-sm" placeholder="/path/to/target" value={targetDir} onChange={e => setTargetDir(e.target.value)} />
          </div>
        </div>

        {profileDetail && (
          <div className="text-xs text-gray-500 bg-gray-50 rounded p-2">
            <span className="font-medium">{profileDetail.description}</span>
            {' | Match: '}
            {profileDetail.match_key.segment
              ? `${profileDetail.match_key.segment}:${profileDetail.match_key.field}`
              : `json_path:${profileDetail.match_key.json_path}`}
            {' | Qualifiers: '}
            {Object.entries(profileDetail.segment_qualifiers || {}).map(([k, v]) => `${k}=${v || 'pos'}`).join(', ') || 'none'}
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={runComparison}
            disabled={running || !selectedProfile || !sourceDir || !targetDir}
            className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {running ? 'Running...' : 'Run Comparison'}
          </button>
          {selectedProfile && (
            <button onClick={loadRules} className="border border-gray-300 px-4 py-1.5 rounded text-sm hover:bg-gray-50">
              {showRules ? 'Reload Rules' : 'Edit Rules'}
            </button>
          )}
          {selectedRun && (
            <a
              href={api.compareExportUrl(selectedRun.run_id)}
              className="border border-gray-300 px-4 py-1.5 rounded text-sm hover:bg-gray-50 inline-block"
            >
              Export CSV
            </a>
          )}
          {selectedRun && (
            <button
              onClick={reclassifyRun}
              disabled={reclassifying}
              className="border border-gray-300 px-4 py-1.5 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              {reclassifying ? 'Reclassifying...' : 'Reclassify'}
            </button>
          )}
        </div>
      </div>

      {/* Rules Editor */}
      {showRules && (
        <div className="bg-white rounded-lg shadow p-4 mb-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold text-sm text-gray-500 uppercase">Rules: {selectedProfile}</h2>
            <button onClick={() => setShowRules(false)} className="text-gray-400 hover:text-gray-600 text-sm">&times; Close</button>
          </div>
          <textarea
            className="w-full h-64 border rounded p-2 text-xs font-mono"
            value={rulesJson}
            onChange={e => setRulesJson(e.target.value)}
          />
          <button
            onClick={saveRules}
            disabled={rulesSaving}
            className="mt-2 bg-green-600 text-white px-4 py-1.5 rounded text-sm hover:bg-green-700 disabled:opacity-50"
          >
            {rulesSaving ? 'Saving...' : 'Save Rules'}
          </button>
        </div>
      )}

      {/* Run History */}
      <div className="bg-white rounded-lg shadow p-4 mb-4">
        <h2 className="font-semibold text-sm text-gray-500 uppercase mb-2">Run History</h2>
        {checkedRuns.size === 2 && (
          <button
            onClick={diffSelectedRuns}
            disabled={diffLoading}
            className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50 mb-2"
          >
            {diffLoading ? 'Comparing...' : 'Diff Selected'}
          </button>
        )}
        {runs.length === 0 ? (
          <p className="text-sm text-gray-400">No comparison runs yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b">
                <th className="py-1 pr-2 w-8"></th>
                <th className="py-1 pr-2">Run #</th>
                <th className="py-1 pr-2">Date</th>
                <th className="py-1 pr-2">Profile</th>
                <th className="py-1 pr-2">Pairs</th>
                <th className="py-1 pr-2">Match</th>
                <th className="py-1 pr-2">Diff</th>
                <th className="py-1 pr-2">Unmatched</th>
              </tr>
            </thead>
            <tbody>
              {runs.map(r => (
                <tr
                  key={r.run_id}
                  onClick={() => selectRun(r)}
                  className={`cursor-pointer hover:bg-blue-50 ${selectedRun?.run_id === r.run_id ? 'bg-blue-50' : ''}`}
                >
                  <td className="py-1 pr-2" onClick={e => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={checkedRuns.has(r.run_id)}
                      onChange={() => toggleRunCheck(r.run_id)}
                      disabled={!checkedRuns.has(r.run_id) && checkedRuns.size >= 2}
                      className="rounded"
                    />
                  </td>
                  <td className="py-1 pr-2 font-mono">
                    {r.run_id}
                    {r.reclassified_from && (
                      <span className="ml-1 px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">
                        re:{r.reclassified_from}
                      </span>
                    )}
                  </td>
                  <td className="py-1 pr-2">{r.started_at?.slice(0, 19)}</td>
                  <td className="py-1 pr-2">{r.profile}</td>
                  <td className="py-1 pr-2">{r.total_pairs}</td>
                  <td className="py-1 pr-2 text-green-600">{r.matched}</td>
                  <td className="py-1 pr-2 text-red-600">{r.mismatched}</td>
                  <td className="py-1 pr-2 text-yellow-600">{r.unmatched}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Run Diff Results */}
      {runDiff && (
        <div className="bg-white rounded-lg shadow p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-sm text-gray-500 uppercase">
              Run Diff: {Array.from(checkedRuns).sort((a,b)=>a-b).join(' vs ')}
            </h2>
            <button onClick={() => setRunDiff(null)} className="text-gray-400 hover:text-gray-600 text-sm">&times; Close</button>
          </div>
          <div className="grid grid-cols-4 gap-3 mb-4">
            <div className="bg-red-50 rounded p-3 text-center">
              <div className="text-2xl font-bold text-red-600">{runDiff.new_errors?.length || 0}</div>
              <div className="text-xs text-gray-500">New Errors</div>
            </div>
            <div className="bg-green-50 rounded p-3 text-center">
              <div className="text-2xl font-bold text-green-600">{runDiff.resolved_errors?.length || 0}</div>
              <div className="text-xs text-gray-500">Resolved</div>
            </div>
            <div className="bg-yellow-50 rounded p-3 text-center">
              <div className="text-2xl font-bold text-yellow-600">{runDiff.changed_errors?.length || 0}</div>
              <div className="text-xs text-gray-500">Changed</div>
            </div>
            <div className="bg-gray-50 rounded p-3 text-center">
              <div className="text-2xl font-bold text-gray-600">{runDiff.unchanged_count || 0}</div>
              <div className="text-xs text-gray-500">Unchanged</div>
            </div>
          </div>

          {runDiff.new_errors?.length > 0 && (
            <div className="mb-3">
              <h3 className="text-xs text-gray-500 uppercase mb-1">New Errors</h3>
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-gray-500 border-b">
                  <th className="py-1 pr-2">Segment</th><th className="py-1 pr-2">Field</th><th className="py-1 pr-2">Severity</th>
                </tr></thead>
                <tbody>
                  {runDiff.new_errors.map((e: any, i: number) => (
                    <tr key={i} className="border-b border-gray-50">
                      <td className="py-1 pr-2 font-mono text-xs">{e.segment}</td>
                      <td className="py-1 pr-2 font-mono text-xs">{e.field}</td>
                      <td className="py-1 pr-2"><StatusBadge status={e.severity} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {runDiff.resolved_errors?.length > 0 && (
            <div className="mb-3">
              <h3 className="text-xs text-gray-500 uppercase mb-1">Resolved Errors</h3>
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-gray-500 border-b">
                  <th className="py-1 pr-2">Segment</th><th className="py-1 pr-2">Field</th><th className="py-1 pr-2">Severity</th>
                </tr></thead>
                <tbody>
                  {runDiff.resolved_errors.map((e: any, i: number) => (
                    <tr key={i} className="border-b border-gray-50">
                      <td className="py-1 pr-2 font-mono text-xs">{e.segment}</td>
                      <td className="py-1 pr-2 font-mono text-xs">{e.field}</td>
                      <td className="py-1 pr-2"><StatusBadge status={e.severity} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {runDiff.changed_errors?.length > 0 && (
            <div className="mb-3">
              <h3 className="text-xs text-gray-500 uppercase mb-1">Changed Errors</h3>
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-gray-500 border-b">
                  <th className="py-1 pr-2">Segment</th><th className="py-1 pr-2">Field</th>
                  <th className="py-1 pr-2">Old</th><th className="py-1 pr-2">New</th>
                </tr></thead>
                <tbody>
                  {runDiff.changed_errors.map((e: any, i: number) => (
                    <tr key={i} className="border-b border-gray-50">
                      <td className="py-1 pr-2 font-mono text-xs">{e.segment}</td>
                      <td className="py-1 pr-2 font-mono text-xs">{e.field}</td>
                      <td className="py-1 pr-2"><StatusBadge status={e.old_severity || e.severity_a} /></td>
                      <td className="py-1 pr-2"><StatusBadge status={e.new_severity || e.severity_b} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Run Detail — Pairs */}
      {selectedRun && (
        <div className="bg-white rounded-lg shadow p-4 mb-4">
          <div className="flex items-center gap-2 mb-2">
            <h2 className="font-semibold text-sm text-gray-500 uppercase">
              Run #{selectedRun.run_id} — Pairs
            </h2>
            <div className="flex gap-1">
              {['', 'MATCH', 'MISMATCH', 'UNMATCHED'].map(s => (
                <button
                  key={s}
                  onClick={() => filterPairs(s)}
                  className={`px-2 py-0.5 rounded text-xs ${statusFilter === s ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                >
                  {s || 'All'}
                </button>
              ))}
            </div>
          </div>
          {loading ? (
            <p className="text-sm text-gray-400">Loading...</p>
          ) : pairs.length === 0 ? (
            <p className="text-sm text-gray-400">No pairs found.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b">
                  <th className="py-1 pr-2">Source File</th>
                  <th className="py-1 pr-2">Target File</th>
                  <th className="py-1 pr-2">Match Value</th>
                  <th className="py-1 pr-2">Status</th>
                  <th className="py-1 pr-2">Diffs</th>
                </tr>
              </thead>
              <tbody>
                {pairs.map(p => (
                  <tr
                    key={p.id}
                    onClick={() => p.status !== 'MATCH' && selectPair(p)}
                    className={`${p.status !== 'MATCH' ? 'cursor-pointer hover:bg-blue-50' : ''} ${selectedPair?.id === p.id ? 'bg-blue-50' : ''}`}
                  >
                    <td className="py-1 pr-2 font-mono text-xs truncate max-w-48">{p.source_file?.split(/[/\\]/).pop()}</td>
                    <td className="py-1 pr-2 font-mono text-xs truncate max-w-48">{p.target_file?.split(/[/\\]/).pop() || '—'}</td>
                    <td className="py-1 pr-2">{p.match_value}</td>
                    <td className="py-1 pr-2"><StatusBadge status={p.status} /></td>
                    <td className="py-1 pr-2">{p.diff_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Summary Statistics */}
      {selectedRun && summary && (
        <div className="bg-white rounded-lg shadow p-4 mb-4">
          <h2 className="font-semibold text-sm text-gray-500 uppercase mb-3">
            Run #{selectedRun.run_id} — Summary
          </h2>
          <div className="grid grid-cols-2 gap-4">
            {/* Severity Breakdown */}
            <div>
              <h3 className="text-xs text-gray-500 mb-2 uppercase">Severity</h3>
              {Object.entries(summary.severity || {}).map(([sev, count]: [string, any]) => {
                const max = Math.max(...Object.values(summary.severity || {}).map(Number))
                const pct = max > 0 ? (Number(count) / max) * 100 : 0
                const barColor = sev === 'hard' ? 'bg-red-300' : sev === 'soft' ? 'bg-yellow-300' : 'bg-gray-300'
                return (
                  <div key={sev} className="flex items-center gap-2 mb-1">
                    <StatusBadge status={sev} />
                    <div className="flex-1 bg-gray-100 rounded h-2">
                      <div className={`${barColor} h-2 rounded`} style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs text-gray-600 w-8 text-right">{String(count)}</span>
                  </div>
                )
              })}
            </div>

            {/* Segment Breakdown */}
            <div>
              <h3 className="text-xs text-gray-500 mb-2 uppercase">By Segment</h3>
              <div className="max-h-40 overflow-auto">
                {Object.entries(summary.segments || {})
                  .sort(([,a]: any, [,b]: any) => b - a)
                  .map(([seg, count]: [string, any]) => {
                    const max = Math.max(...Object.values(summary.segments || {}).map(Number))
                    const pct = max > 0 ? (Number(count) / max) * 100 : 0
                    return (
                      <div key={seg} className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono w-20 truncate">{seg}</span>
                        <div className="flex-1 bg-gray-100 rounded h-2">
                          <div className="bg-blue-300 h-2 rounded" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-xs text-gray-600 w-8 text-right">{String(count)}</span>
                      </div>
                    )
                  })}
              </div>
            </div>

            {/* Field Breakdown */}
            <div>
              <h3 className="text-xs text-gray-500 mb-2 uppercase">By Field</h3>
              <div className="max-h-40 overflow-auto">
                {Object.entries(summary.fields || {})
                  .sort(([,a]: any, [,b]: any) => b - a)
                  .map(([field, count]: [string, any]) => {
                    const max = Math.max(...Object.values(summary.fields || {}).map(Number))
                    const pct = max > 0 ? (Number(count) / max) * 100 : 0
                    return (
                      <div key={field} className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono w-24 truncate">{field}</span>
                        <div className="flex-1 bg-gray-100 rounded h-2">
                          <div className="bg-blue-300 h-2 rounded" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-xs text-gray-600 w-8 text-right">{String(count)}</span>
                      </div>
                    )
                  })}
              </div>
            </div>

            {/* Top 10 Errors */}
            <div>
              <h3 className="text-xs text-gray-500 mb-2 uppercase">Top Errors</h3>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-gray-500 border-b">
                    <th className="py-1 pr-2">Segment</th>
                    <th className="py-1 pr-2">Field</th>
                    <th className="py-1 pr-2 text-right">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {(summary.top_errors || []).map((e: any, i: number) => (
                    <tr key={i} className="border-b border-gray-50">
                      <td className="py-1 pr-2 font-mono">{e.segment}</td>
                      <td className="py-1 pr-2 font-mono">{e.field}</td>
                      <td className="py-1 pr-2 text-right">{e.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Pair Detail — Diffs */}
      {selectedPair && diffs.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4 mb-4">
          <h2 className="font-semibold text-sm text-gray-500 uppercase mb-2">
            Diffs — {selectedPair.match_value}
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b">
                <th className="py-1 pr-2">Segment</th>
                <th className="py-1 pr-2">Field</th>
                <th className="py-1 pr-2">Severity</th>
                <th className="py-1 pr-2">Source</th>
                <th className="py-1 pr-2">Target</th>
                <th className="py-1 pr-2">Description</th>
              </tr>
            </thead>
            <tbody>
              {diffs.map((d, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-1 pr-2 font-mono text-xs">{d.segment}</td>
                  <td className="py-1 pr-2 font-mono text-xs">{d.field}</td>
                  <td className="py-1 pr-2"><StatusBadge status={d.severity} /></td>
                  <td className="py-1 pr-2 text-xs">{d.source_value ?? '—'}</td>
                  <td className="py-1 pr-2 text-xs">{d.target_value ?? '—'}</td>
                  <td className="py-1 pr-2 text-xs text-gray-500">{d.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      </>
      )}

      {view === 'discoveries' && (
        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="font-semibold text-sm text-gray-500 uppercase mb-3">Error Discoveries</h2>

          {/* Profile selector */}
          <div className="mb-3">
            <label className="block text-xs text-gray-500 mb-1">Profile</label>
            <select
              className="border rounded px-3 py-1.5 text-sm"
              value={selectedProfile}
              onChange={e => setSelectedProfile(e.target.value)}
            >
              <option value="">Select profile...</option>
              {profiles.map(p => (
                <option key={p.name} value={p.name}>{p.name}</option>
              ))}
            </select>
          </div>

          {!selectedProfile ? (
            <p className="text-sm text-gray-400">Select a profile to view discoveries.</p>
          ) : (
            <>
              {/* Filter buttons */}
              <div className="flex gap-1 mb-3">
                {['all', 'pending', 'applied'].map(f => (
                  <button
                    key={f}
                    onClick={() => setDiscoveryFilter(f)}
                    className={`px-2 py-0.5 rounded text-xs capitalize ${discoveryFilter === f ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                  >
                    {f}
                  </button>
                ))}
              </div>

              {discoveryLoading ? (
                <p className="text-sm text-gray-400">Loading...</p>
              ) : discoveries.length === 0 ? (
                <p className="text-sm text-gray-400">No discoveries found.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 border-b">
                      <th className="py-1 pr-2">Segment</th>
                      <th className="py-1 pr-2">Field</th>
                      <th className="py-1 pr-2">Source Value</th>
                      <th className="py-1 pr-2">Target Value</th>
                      <th className="py-1 pr-2">Severity</th>
                      <th className="py-1 pr-2">Status</th>
                      <th className="py-1 pr-2">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {discoveries.map(d => (
                      <tr key={d.id} className="border-b border-gray-50">
                        <td className="py-1 pr-2 font-mono text-xs">{d.segment}</td>
                        <td className="py-1 pr-2 font-mono text-xs">{d.field}</td>
                        <td className="py-1 pr-2 text-xs">{d.source_value ?? '—'}</td>
                        <td className="py-1 pr-2 text-xs">{d.target_value ?? '—'}</td>
                        <td className="py-1 pr-2"><StatusBadge status={d.suggested_severity} /></td>
                        <td className="py-1 pr-2">
                          {d.applied
                            ? <span className="px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">Applied</span>
                            : <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">Pending</span>
                          }
                        </td>
                        <td className="py-1 pr-2">
                          {!d.applied && (
                            <button
                              onClick={() => applyDiscovery(d.id)}
                              disabled={applyingId === d.id}
                              className="bg-green-600 text-white px-2 py-0.5 rounded text-xs hover:bg-green-700 disabled:opacity-50"
                            >
                              {applyingId === d.id ? '...' : 'Apply'}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
