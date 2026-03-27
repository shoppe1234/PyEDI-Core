import { useState, useEffect, useRef } from 'react'
import { api } from '../api'

/* ═══════════════════════════════════════════════════════════════════════════
   TYPES
   ═══════════════════════════════════════════════════════════════════════════ */

interface TierInfo {
  tier: string
  name: string
  file: string
  rule_count: number
  ignore_count: number
}

interface ClassificationRule {
  segment: string
  field: string
  severity: string
  ignore_case: boolean
  numeric: boolean
  conditional_qualifier?: string | null
  amount_variance?: number | null
}

interface IgnoreEntry {
  segment: string
  field: string
  reason: string
}

interface EffectiveRule extends ClassificationRule {
  tier: string
}

interface SegmentOption {
  name: string
  label: string
  fields: string[]
}

type Tab = 'overview' | 'universal' | 'transaction' | 'partner' | 'effective'

const TABS: { key: Tab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'universal', label: 'Universal' },
  { key: 'transaction', label: 'Transaction' },
  { key: 'partner', label: 'Partner' },
  { key: 'effective', label: 'Effective View' },
]

const TIER_ORDER: Record<string, number> = { partner: 0, transaction: 1, universal: 2, default: 3 }

/* ═══════════════════════════════════════════════════════════════════════════
   TIER BADGE
   ═══════════════════════════════════════════════════════════════════════════ */

function TierBadge({ tier }: { tier: string }) {
  const colors: Record<string, string> = {
    universal: 'bg-blue-100 text-blue-700 ring-blue-200',
    transaction: 'bg-amber-100 text-amber-700 ring-amber-200',
    partner: 'bg-emerald-100 text-emerald-700 ring-emerald-200',
    default: 'bg-gray-100 text-gray-500 ring-gray-200',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold ring-1 ring-inset ${colors[tier] || colors.default}`}>
      {tier}
    </span>
  )
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    hard: 'bg-red-100 text-red-700',
    soft: 'bg-amber-100 text-amber-700',
    ignore: 'bg-gray-100 text-gray-500',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[severity] || 'bg-gray-100 text-gray-600'}`}>
      {severity}
    </span>
  )
}

function CountBadge({ count, label, color }: { count: number; label: string; color: string }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${color}`}>
      <span className="font-bold">{count}</span> {label}
    </span>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════
   FIELD COMBOBOX (searchable dropdown with manual entry)
   ═══════════════════════════════════════════════════════════════════════════ */

function FieldCombobox({
  value,
  options,
  onChange,
  placeholder,
}: {
  value: string
  options: string[]
  onChange: (v: string) => void
  placeholder?: string
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = options.filter(o =>
    o.toLowerCase().includes((search || value).toLowerCase())
  )

  const hasOptions = options.length > 0

  return (
    <div ref={ref} className="relative">
      <input
        value={open ? search : value}
        onChange={e => {
          setSearch(e.target.value)
          onChange(e.target.value)
          if (!open && hasOptions) setOpen(true)
        }}
        onFocus={() => { setSearch(value); if (hasOptions) setOpen(true) }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder={placeholder}
        className="w-full px-2 py-1 border border-gray-200 rounded text-xs font-mono focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none pr-6"
      />
      {hasOptions && (
        <button
          type="button"
          tabIndex={-1}
          onClick={() => { setSearch(value); setOpen(!open) }}
          className="absolute right-1 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d={open ? "M5 15l7-7 7 7" : "M19 9l-7 7-7-7"} />
          </svg>
        </button>
      )}
      {open && filtered.length > 0 && (
        <div className="absolute z-50 mt-1 w-full max-h-48 overflow-auto bg-white border border-gray-200 rounded-lg shadow-lg">
          {filtered.map(o => (
            <button
              key={o}
              type="button"
              onMouseDown={e => {
                e.preventDefault()
                onChange(o)
                setSearch(o)
                setOpen(false)
              }}
              className={`w-full text-left px-2 py-1.5 text-xs font-mono hover:bg-blue-50 transition-colors ${
                o === value ? 'bg-blue-50 text-blue-700 font-semibold' : 'text-gray-700'
              }`}
            >
              {o}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════
   RULES GRID (reusable)
   ═══════════════════════════════════════════════════════════════════════════ */

function RulesGrid({
  rules,
  ignores,
  onChange,
  onIgnoreChange,
  readOnly = false,
  fieldOptions = [],
}: {
  rules: ClassificationRule[]
  ignores: IgnoreEntry[]
  onChange?: (rules: ClassificationRule[]) => void
  onIgnoreChange?: (ignores: IgnoreEntry[]) => void
  readOnly?: boolean
  fieldOptions?: SegmentOption[]
}) {
  const updateRule = (idx: number, patch: Partial<ClassificationRule>) => {
    if (!onChange) return
    const next = rules.map((r, i) => (i === idx ? { ...r, ...patch } : r))
    onChange(next)
  }

  const removeRule = (idx: number) => {
    if (!onChange) return
    onChange(rules.filter((_, i) => i !== idx))
  }

  const addRule = () => {
    if (!onChange) return
    onChange([...rules, { segment: '*', field: '', severity: 'hard', ignore_case: false, numeric: false }])
  }

  const updateIgnore = (idx: number, patch: Partial<IgnoreEntry>) => {
    if (!onIgnoreChange) return
    const next = ignores.map((e, i) => (i === idx ? { ...e, ...patch } : e))
    onIgnoreChange(next)
  }

  const removeIgnore = (idx: number) => {
    if (!onIgnoreChange) return
    onIgnoreChange(ignores.filter((_, i) => i !== idx))
  }

  const addIgnore = () => {
    if (!onIgnoreChange) return
    onIgnoreChange([...ignores, { segment: '*', field: '', reason: '' }])
  }

  return (
    <div className="space-y-6">
      {/* Classification Rules */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider">Classification Rules</h3>
          {!readOnly && (
            <button onClick={addRule} className="text-xs font-medium text-blue-600 hover:text-blue-800 transition-colors">
              + Add Rule
            </button>
          )}
        </div>
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Segment</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Field</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Severity</th>
                <th className="px-3 py-2.5 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">Numeric</th>
                <th className="px-3 py-2.5 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">Ignore Case</th>
                {!readOnly && <th className="px-3 py-2.5 w-10"></th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rules.length === 0 && (
                <tr><td colSpan={readOnly ? 5 : 6} className="px-3 py-6 text-center text-gray-400 text-sm italic">No classification rules</td></tr>
              )}
              {rules.map((r, i) => {
                const segmentNames = fieldOptions.map(s => s.name)
                const matchedSeg = fieldOptions.find(s => s.name === r.segment)
                const fieldNames = matchedSeg
                  ? matchedSeg.fields
                  : fieldOptions.flatMap(s => s.fields)
                return (
                <tr key={i} className="even:bg-gray-50/60 hover:bg-blue-50/40 transition-colors">
                  <td className="px-3 py-2">
                    {readOnly ? <span className="font-mono text-xs">{r.segment}</span> : (
                      <FieldCombobox
                        value={r.segment}
                        options={segmentNames}
                        onChange={v => updateRule(i, { segment: v })}
                        placeholder="e.g. N1 or *"
                      />
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {readOnly ? <span className="font-mono text-xs">{r.field}</span> : (
                      <FieldCombobox
                        value={r.field}
                        options={fieldNames}
                        onChange={v => updateRule(i, { field: v })}
                        placeholder="e.g. N102"
                      />
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {readOnly ? <SeverityBadge severity={r.severity} /> : (
                      <select value={r.severity} onChange={e => updateRule(i, { severity: e.target.value })}
                        className={`px-2 py-1 border rounded text-xs font-medium outline-none focus:ring-1 focus:ring-blue-400 ${
                          r.severity === 'hard' ? 'border-red-200 bg-red-50 text-red-700'
                          : r.severity === 'soft' ? 'border-amber-200 bg-amber-50 text-amber-700'
                          : 'border-gray-200 bg-gray-50 text-gray-500'
                        }`}>
                        <option value="hard">hard</option>
                        <option value="soft">soft</option>
                        <option value="ignore">ignore</option>
                      </select>
                    )}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {readOnly ? (r.numeric ? <span className="text-emerald-600 text-xs font-medium">Yes</span> : <span className="text-gray-300 text-xs">-</span>) : (
                      <input type="checkbox" checked={r.numeric} onChange={e => updateRule(i, { numeric: e.target.checked })}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                    )}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {readOnly ? (r.ignore_case ? <span className="text-emerald-600 text-xs font-medium">Yes</span> : <span className="text-gray-300 text-xs">-</span>) : (
                      <input type="checkbox" checked={r.ignore_case} onChange={e => updateRule(i, { ignore_case: e.target.checked })}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                    )}
                  </td>
                  {!readOnly && (
                    <td className="px-2 py-2 text-center">
                      <button onClick={() => removeRule(i)} className="text-gray-300 hover:text-red-500 transition-colors" title="Remove">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </td>
                  )}
                </tr>
              )})}
            </tbody>
          </table>
        </div>
      </div>

      {/* Ignore List */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider">Ignore List</h3>
          {!readOnly && (
            <button onClick={addIgnore} className="text-xs font-medium text-blue-600 hover:text-blue-800 transition-colors">
              + Add Ignore
            </button>
          )}
        </div>
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Segment</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Field</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Reason</th>
                {!readOnly && <th className="px-3 py-2.5 w-10"></th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {ignores.length === 0 && (
                <tr><td colSpan={readOnly ? 3 : 4} className="px-3 py-6 text-center text-gray-400 text-sm italic">No ignore entries</td></tr>
              )}
              {ignores.map((e, i) => {
                const segmentNames = fieldOptions.map(s => s.name)
                const matchedSeg = fieldOptions.find(s => s.name === e.segment)
                const fieldNames = matchedSeg
                  ? matchedSeg.fields
                  : fieldOptions.flatMap(s => s.fields)
                return (
                <tr key={i} className="even:bg-gray-50/60 hover:bg-blue-50/40 transition-colors">
                  <td className="px-3 py-2">
                    {readOnly ? <span className="font-mono text-xs">{e.segment}</span> : (
                      <FieldCombobox
                        value={e.segment}
                        options={segmentNames}
                        onChange={v => updateIgnore(i, { segment: v })}
                        placeholder="e.g. N1 or *"
                      />
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {readOnly ? <span className="font-mono text-xs">{e.field}</span> : (
                      <FieldCombobox
                        value={e.field}
                        options={fieldNames}
                        onChange={v => updateIgnore(i, { field: v })}
                        placeholder="e.g. N102"
                      />
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {readOnly ? <span className="text-xs text-gray-600">{e.reason}</span> : (
                      <input value={e.reason} onChange={ev => updateIgnore(i, { reason: ev.target.value })}
                        className="w-full px-2 py-1 border border-gray-200 rounded text-xs focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none" />
                    )}
                  </td>
                  {!readOnly && (
                    <td className="px-2 py-2 text-center">
                      <button onClick={() => removeIgnore(i)} className="text-gray-300 hover:text-red-500 transition-colors" title="Remove">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </td>
                  )}
                </tr>
              )})}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN PAGE
   ═══════════════════════════════════════════════════════════════════════════ */

export default function RulesPage({ onNavigate }: { onNavigate?: (page: string) => void }) {
  const [tab, setTab] = useState<Tab>('overview')
  const [tiers, setTiers] = useState<TierInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Universal editor state
  const [uniRules, setUniRules] = useState<ClassificationRule[]>([])
  const [uniIgnores, setUniIgnores] = useState<IgnoreEntry[]>([])
  const [uniSaving, setUniSaving] = useState(false)
  const [uniSuccess, setUniSuccess] = useState(false)

  // Transaction editor state
  const [txnTypes, setTxnTypes] = useState<string[]>([])
  const [selectedTxn, setSelectedTxn] = useState('')
  const [newTxnType, setNewTxnType] = useState('')
  const [showNewTxn, setShowNewTxn] = useState(false)
  const [txnRules, setTxnRules] = useState<ClassificationRule[]>([])
  const [txnIgnores, setTxnIgnores] = useState<IgnoreEntry[]>([])
  const [txnSaving, setTxnSaving] = useState(false)
  const [txnSuccess, setTxnSuccess] = useState(false)
  const [txnDeleting, setTxnDeleting] = useState(false)
  const [txnConfirmDelete, setTxnConfirmDelete] = useState(false)

  // Partner editor state
  const [selectedPartner, setSelectedPartner] = useState('')
  const [partnerRules, setPartnerRules] = useState<ClassificationRule[]>([])
  const [partnerIgnores, setPartnerIgnores] = useState<IgnoreEntry[]>([])
  const [partnerSaving, setPartnerSaving] = useState(false)
  const [partnerSuccess, setPartnerSuccess] = useState(false)

  // Effective view state
  const [profiles, setProfiles] = useState<any[]>([])
  const [selectedProfile, setSelectedProfile] = useState('')
  const [effectiveRules, setEffectiveRules] = useState<EffectiveRule[]>([])
  const [effectiveIgnores, setEffectiveIgnores] = useState<IgnoreEntry[]>([])
  const [effectiveLoading, setEffectiveLoading] = useState(false)

  // Field options state (dropdown data)
  const [uniFormat, setUniFormat] = useState<string>('edi')
  const [uniFieldOpts, setUniFieldOpts] = useState<SegmentOption[]>([])
  const [txnFieldOpts, setTxnFieldOpts] = useState<SegmentOption[]>([])
  const [partnerFieldOpts, setPartnerFieldOpts] = useState<SegmentOption[]>([])

  // Load tiers on mount
  useEffect(() => {
    loadTiers()
    api.compareProfiles().then(setProfiles).catch(e => setError(e.message))
  }, [])

  const loadTiers = () => {
    setLoading(true)
    api.ruleTiers()
      .then(d => {
        setTiers(d.tiers)
        const types = d.tiers
          .filter(t => t.tier === 'transaction')
          .map(t => t.file.replace('_global_', '').replace('.yaml', ''))
        setTxnTypes(types)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  // Load universal rules when switching to that tab
  useEffect(() => {
    if (tab === 'universal') {
      api.ruleUniversal().then(d => {
        setUniRules((d.classification || []).map(normRule))
        setUniIgnores((d.ignore || []).map(normIgnore))
      }).catch(e => setError(e.message))
    }
  }, [tab])

  // Load transaction rules when selection changes
  useEffect(() => {
    if (selectedTxn && tab === 'transaction') {
      api.ruleTransaction(selectedTxn).then(d => {
        setTxnRules((d.classification || []).map(normRule))
        setTxnIgnores((d.ignore || []).map(normIgnore))
      }).catch(e => {
        setTxnRules([])
        setTxnIgnores([])
      })
    }
  }, [selectedTxn, tab])

  // Load partner rules when selection changes
  useEffect(() => {
    if (selectedPartner && tab === 'partner') {
      api.compareRules(selectedPartner).then(d => {
        setPartnerRules((d.classification || []).map(normRule))
        setPartnerIgnores((d.ignore || []).map(normIgnore))
      }).catch(e => {
        setPartnerRules([])
        setPartnerIgnores([])
      })
    }
  }, [selectedPartner, tab])

  // Load effective rules when profile changes
  useEffect(() => {
    if (selectedProfile && tab === 'effective') {
      setEffectiveLoading(true)
      api.ruleEffective(selectedProfile).then(d => {
        const sorted = [...d.rules].sort((a, b) =>
          (TIER_ORDER[a.tier] ?? 9) - (TIER_ORDER[b.tier] ?? 9)
        )
        setEffectiveRules(sorted)
        setEffectiveIgnores((d.ignore || []).map(normIgnore))
      }).catch(e => setError(e.message))
        .finally(() => setEffectiveLoading(false))
    }
  }, [selectedProfile, tab])

  // Load field options for Universal tier when format changes
  useEffect(() => {
    if (tab === 'universal') {
      api.ruleFieldOptions({ format: uniFormat })
        .then(d => setUniFieldOpts(d.segments))
        .catch(() => setUniFieldOpts([]))
    }
  }, [tab, uniFormat])

  // Load field options for Transaction tier
  useEffect(() => {
    if (selectedTxn && tab === 'transaction') {
      api.ruleFieldOptions({ transaction_type: selectedTxn })
        .then(d => setTxnFieldOpts(d.segments))
        .catch(() => setTxnFieldOpts([]))
    }
  }, [selectedTxn, tab])

  // Load field options for Partner tier
  useEffect(() => {
    if (selectedPartner && tab === 'partner') {
      api.ruleFieldOptions({ profile: selectedPartner })
        .then(d => setPartnerFieldOpts(d.segments))
        .catch(() => setPartnerFieldOpts([]))
    }
  }, [selectedPartner, tab])

  const normRule = (r: any): ClassificationRule => ({
    segment: r.segment || '*',
    field: r.field || '',
    severity: r.severity || 'hard',
    ignore_case: !!r.ignore_case,
    numeric: !!r.numeric,
    conditional_qualifier: r.conditional_qualifier ?? null,
    amount_variance: r.amount_variance ?? null,
  })

  const normIgnore = (e: any): IgnoreEntry => ({
    segment: e.segment || '*',
    field: e.field || '*',
    reason: e.reason || '',
  })

  /* ── Save handlers ── */

  const saveUniversal = () => {
    setUniSaving(true)
    setUniSuccess(false)
    api.ruleUpdateUniversal({ classification: uniRules, ignore: uniIgnores })
      .then(() => { setUniSuccess(true); loadTiers(); setTimeout(() => setUniSuccess(false), 3000) })
      .catch(e => setError(e.message))
      .finally(() => setUniSaving(false))
  }

  const saveTransaction = () => {
    if (!selectedTxn) return
    setTxnSaving(true)
    setTxnSuccess(false)
    api.ruleUpdateTransaction(selectedTxn, { classification: txnRules, ignore: txnIgnores })
      .then(() => { setTxnSuccess(true); loadTiers(); setTimeout(() => setTxnSuccess(false), 3000) })
      .catch(e => setError(e.message))
      .finally(() => setTxnSaving(false))
  }

  const createTxnType = () => {
    const code = newTxnType.trim()
    if (!code) return
    api.ruleUpdateTransaction(code, { classification: [], ignore: [] })
      .then(() => {
        setShowNewTxn(false)
        setNewTxnType('')
        setSelectedTxn(code)
        loadTiers()
      })
      .catch(e => setError(e.message))
  }

  const deleteTxnType = () => {
    if (!selectedTxn) return
    setTxnDeleting(true)
    api.ruleDeleteTransaction(selectedTxn)
      .then(() => {
        setSelectedTxn('')
        setTxnRules([])
        setTxnIgnores([])
        setTxnConfirmDelete(false)
        loadTiers()
      })
      .catch(e => setError(e.message))
      .finally(() => setTxnDeleting(false))
  }

  const savePartner = () => {
    if (!selectedPartner) return
    setPartnerSaving(true)
    setPartnerSuccess(false)
    api.compareUpdateRules(selectedPartner, { classification: partnerRules, ignore: partnerIgnores })
      .then(() => { setPartnerSuccess(true); loadTiers(); setTimeout(() => setPartnerSuccess(false), 3000) })
      .catch(e => setError(e.message))
      .finally(() => setPartnerSaving(false))
  }

  /* ── Computed ── */

  const universalTier = tiers.find(t => t.tier === 'universal')
  const txnTiers = tiers.filter(t => t.tier === 'transaction')
  const partnerTiers = tiers.filter(t => t.tier === 'partner')

  const effectiveSummary = effectiveRules.reduce(
    (acc, r) => {
      acc[r.tier] = (acc[r.tier] || 0) + 1
      return acc
    },
    {} as Record<string, number>,
  )

  /* ═══════════════════════════════════════════════════════════════════════
     RENDER
     ═══════════════════════════════════════════════════════════════════════ */

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Rules Management</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage the 3-tier rule hierarchy: Universal &rarr; Transaction-type &rarr; Partner
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-red-400 hover:text-red-600 text-lg leading-none">&times;</button>
        </div>
      )}

      {/* Tab bar */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`pb-3 text-sm transition-colors ${
                tab === t.key
                  ? 'border-b-2 border-blue-600 text-blue-600 font-medium'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {tab === 'overview' && (
        <div className="space-y-5">
          {/* Universal card */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Universal Rules</h2>
                <p className="text-sm text-gray-500 mt-0.5">Apply to all profiles — envelope fields, common ignores</p>
                <div className="flex gap-2 mt-3">
                  <CountBadge count={universalTier?.rule_count ?? 0} label="classification" color="bg-blue-50 text-blue-700" />
                  <CountBadge count={universalTier?.ignore_count ?? 0} label="ignore" color="bg-gray-100 text-gray-600" />
                </div>
              </div>
              <button
                onClick={() => setTab('universal')}
                className="px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
              >
                Edit
              </button>
            </div>
          </div>

          {/* Transaction-type card */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Transaction-Type Rules</h2>
                <p className="text-sm text-gray-500 mt-0.5">Apply to all profiles of a given transaction type</p>
              </div>
              <button
                onClick={() => { setTab('transaction'); setShowNewTxn(true) }}
                className="px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
              >
                + Add Type
              </button>
            </div>
            {txnTiers.length === 0 ? (
              <p className="text-sm text-gray-400 italic">No transaction-type rules configured yet</p>
            ) : (
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Type</th>
                      <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Rules</th>
                      <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Ignores</th>
                      <th className="px-4 py-2.5 w-20"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {txnTiers.map(t => {
                      const code = t.file.replace('_global_', '').replace('.yaml', '')
                      return (
                        <tr key={t.file} className="hover:bg-blue-50/40 transition-colors">
                          <td className="px-4 py-2.5 font-medium text-gray-900">{code}</td>
                          <td className="px-4 py-2.5"><CountBadge count={t.rule_count} label="" color="bg-blue-50 text-blue-700" /></td>
                          <td className="px-4 py-2.5"><CountBadge count={t.ignore_count} label="" color="bg-gray-100 text-gray-600" /></td>
                          <td className="px-4 py-2.5 text-right">
                            <button onClick={() => { setSelectedTxn(code); setTab('transaction') }}
                              className="text-xs font-medium text-blue-600 hover:text-blue-800">Edit</button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Partner rules card */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">Partner Rules</h2>
            <p className="text-sm text-gray-500 mb-4">Profile-specific overrides — most specific tier wins</p>
            {partnerTiers.length === 0 ? (
              <p className="text-sm text-gray-400 italic">No partner profiles configured</p>
            ) : (
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Profile</th>
                      <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Rules</th>
                      <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Ignores</th>
                      <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Inherits</th>
                      <th className="px-4 py-2.5 w-20"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {partnerTiers.map(t => {
                      const profile = profiles.find(p => p.name === t.name)
                      const txnType = profile?.transaction_type || ''
                      return (
                        <tr key={t.file} className="hover:bg-blue-50/40 transition-colors">
                          <td className="px-4 py-2.5">
                            <button
                              onClick={() => { setSelectedPartner(t.name); setTab('partner') }}
                              className="font-medium text-blue-600 hover:text-blue-800 hover:underline transition-colors text-left"
                            >
                              {t.name}
                            </button>
                            {profile?.trading_partner && (
                              <div className="text-xs text-gray-400">{profile.trading_partner}</div>
                            )}
                          </td>
                          <td className="px-4 py-2.5"><CountBadge count={t.rule_count} label="" color="bg-emerald-50 text-emerald-700" /></td>
                          <td className="px-4 py-2.5"><CountBadge count={t.ignore_count} label="" color="bg-gray-100 text-gray-600" /></td>
                          <td className="px-4 py-2.5 text-xs text-gray-500">
                            Universal{txnType ? ` + ${txnType}` : ''}
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            <button
                              onClick={() => { setSelectedPartner(t.name); setTab('partner') }}
                              className="text-xs font-medium text-blue-600 hover:text-blue-800"
                            >
                              Edit
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
      )}

      {tab === 'universal' && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold text-gray-900">Universal Rules</h2>
            <button
              onClick={saveUniversal}
              disabled={uniSaving}
              className="px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {uniSaving ? 'Saving...' : 'Save'}
            </button>
          </div>
          {uniSuccess && (
            <div className="mb-4 px-4 py-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700 font-medium">
              Universal rules saved successfully
            </div>
          )}

          {/* Format toggle for field dropdowns */}
          <div className="mb-5 flex items-center gap-2">
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Field format:</span>
            {(['edi', 'csv', 'xml'] as const).map(fmt => (
              <button
                key={fmt}
                onClick={() => setUniFormat(fmt)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  uniFormat === fmt
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {fmt.toUpperCase()}
              </button>
            ))}
          </div>

          <RulesGrid
            rules={uniRules}
            ignores={uniIgnores}
            onChange={setUniRules}
            onIgnoreChange={setUniIgnores}
            fieldOptions={uniFieldOpts}
          />
        </div>
      )}

      {tab === 'transaction' && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Transaction-Type Rules</h2>

          {/* Selector */}
          <div className="flex items-center gap-3 mb-5">
            <select
              value={selectedTxn}
              onChange={e => { setSelectedTxn(e.target.value); setShowNewTxn(false); setTxnConfirmDelete(false) }}
              className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none"
            >
              <option value="">Select transaction type...</option>
              {txnTypes.map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <button
              onClick={() => setShowNewTxn(!showNewTxn)}
              className="text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors"
            >
              + Create New
            </button>
          </div>

          {/* New type form */}
          {showNewTxn && (
            <div className="flex items-center gap-2 mb-5 p-3 bg-blue-50 rounded-lg border border-blue-100">
              <input
                value={newTxnType}
                onChange={e => setNewTxnType(e.target.value)}
                placeholder="Transaction type code (e.g. 850)"
                className="px-3 py-1.5 border border-blue-200 rounded text-sm focus:ring-1 focus:ring-blue-400 outline-none flex-1"
              />
              <button onClick={createTxnType}
                className="px-4 py-1.5 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 transition-colors">
                Create
              </button>
              <button onClick={() => { setShowNewTxn(false); setNewTxnType('') }}
                className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700">Cancel</button>
            </div>
          )}

          {selectedTxn ? (
            <>
              {txnSuccess && (
                <div className="mb-4 px-4 py-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700 font-medium">
                  Transaction rules saved successfully
                </div>
              )}
              <RulesGrid
                rules={txnRules}
                ignores={txnIgnores}
                onChange={setTxnRules}
                onIgnoreChange={setTxnIgnores}
                fieldOptions={txnFieldOpts}
              />
              <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-100">
                <div>
                  {txnConfirmDelete ? (
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-red-600 font-medium">Delete all rules for {selectedTxn}?</span>
                      <button onClick={deleteTxnType} disabled={txnDeleting}
                        className="px-3 py-1.5 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 disabled:opacity-50 transition-colors">
                        {txnDeleting ? 'Deleting...' : 'Confirm'}
                      </button>
                      <button onClick={() => setTxnConfirmDelete(false)}
                        className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700">Cancel</button>
                    </div>
                  ) : (
                    <button onClick={() => setTxnConfirmDelete(true)}
                      className="px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded hover:bg-red-50 transition-colors">
                      Delete Transaction Rules
                    </button>
                  )}
                </div>
                <button
                  onClick={saveTransaction}
                  disabled={txnSaving}
                  className="px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {txnSaving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </>
          ) : (
            <p className="text-sm text-gray-400 italic mt-2">Select a transaction type above, or create a new one</p>
          )}
        </div>
      )}

      {tab === 'partner' && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Partner Rules</h2>
          <p className="text-sm text-gray-500 mb-4">
            Profile-specific overrides — most specific tier. These rules take priority over Universal and Transaction-type rules.
          </p>

          {/* Profile selector */}
          <div className="flex items-center gap-3 mb-5">
            <select
              value={selectedPartner}
              onChange={e => setSelectedPartner(e.target.value)}
              className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none"
            >
              <option value="">Select profile...</option>
              {profiles.map((p: any) => (
                <option key={p.name} value={p.name}>
                  {p.name}{p.trading_partner ? ` (${p.trading_partner})` : ''}
                </option>
              ))}
            </select>
          </div>

          {selectedPartner ? (
            <>
              {partnerSuccess && (
                <div className="mb-4 px-4 py-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700 font-medium">
                  Partner rules saved successfully
                </div>
              )}

              {/* Tier inheritance info */}
              <div className="mb-5 px-4 py-3 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-700">
                These rules override Universal{(() => {
                  const profile = profiles.find((p: any) => p.name === selectedPartner)
                  return profile?.transaction_type ? ` and ${profile.transaction_type} Transaction-type` : ''
                })()} rules for this profile.
              </div>

              <RulesGrid
                rules={partnerRules}
                ignores={partnerIgnores}
                onChange={setPartnerRules}
                onIgnoreChange={setPartnerIgnores}
                fieldOptions={partnerFieldOpts}
              />
              <div className="flex justify-end mt-6 pt-4 border-t border-gray-100">
                <button
                  onClick={savePartner}
                  disabled={partnerSaving}
                  className="px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {partnerSaving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </>
          ) : (
            <p className="text-sm text-gray-400 italic mt-2">Select a profile above to edit its partner-specific rules</p>
          )}
        </div>
      )}

      {tab === 'effective' && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Effective Rules View</h2>

          <select
            value={selectedProfile}
            onChange={e => setSelectedProfile(e.target.value)}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm mb-5 focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none"
          >
            <option value="">Select profile...</option>
            {profiles.map((p: any) => (
              <option key={p.name} value={p.name}>{p.name}{p.trading_partner ? ` (${p.trading_partner})` : ''}</option>
            ))}
          </select>

          {effectiveLoading && <p className="text-sm text-gray-400">Loading...</p>}

          {selectedProfile && !effectiveLoading && effectiveRules.length > 0 && (
            <>
              {/* Summary bar */}
              <div className="flex items-center gap-4 mb-5 px-4 py-3 bg-gray-50 rounded-lg border border-gray-100">
                <span className="text-sm font-medium text-gray-700">
                  {effectiveRules.length} rules total:
                </span>
                {Object.entries(effectiveSummary)
                  .sort(([a], [b]) => (TIER_ORDER[a] ?? 9) - (TIER_ORDER[b] ?? 9))
                  .map(([tier, count]) => (
                    <span key={tier} className="flex items-center gap-1.5">
                      <TierBadge tier={tier} />
                      <span className="text-xs text-gray-500">{count}</span>
                    </span>
                  ))}
              </div>

              {/* Effective rules table */}
              <div className="border border-gray-200 rounded-lg overflow-hidden mb-6">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Segment</th>
                      <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Field</th>
                      <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Severity</th>
                      <th className="px-3 py-2.5 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">Numeric</th>
                      <th className="px-3 py-2.5 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">Ignore Case</th>
                      <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Tier</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {effectiveRules.map((r, i) => (
                      <tr key={i} className="even:bg-gray-50/60 hover:bg-blue-50/40 transition-colors">
                        <td className="px-3 py-2 font-mono text-xs">{r.segment}</td>
                        <td className="px-3 py-2 font-mono text-xs">{r.field}</td>
                        <td className="px-3 py-2"><SeverityBadge severity={r.severity} /></td>
                        <td className="px-3 py-2 text-center">
                          {r.numeric ? <span className="text-emerald-600 text-xs font-medium">Yes</span> : <span className="text-gray-300 text-xs">-</span>}
                        </td>
                        <td className="px-3 py-2 text-center">
                          {r.ignore_case ? <span className="text-emerald-600 text-xs font-medium">Yes</span> : <span className="text-gray-300 text-xs">-</span>}
                        </td>
                        <td className="px-3 py-2"><TierBadge tier={r.tier} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Effective ignores */}
              {effectiveIgnores.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">Merged Ignore List</h3>
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="bg-gray-50 border-b border-gray-200">
                          <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Segment</th>
                          <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Field</th>
                          <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Reason</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {effectiveIgnores.map((e, i) => (
                          <tr key={i} className="even:bg-gray-50/60 hover:bg-blue-50/40 transition-colors">
                            <td className="px-3 py-2 font-mono text-xs">{e.segment}</td>
                            <td className="px-3 py-2 font-mono text-xs">{e.field}</td>
                            <td className="px-3 py-2 text-xs text-gray-600">{e.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}

          {selectedProfile && !effectiveLoading && effectiveRules.length === 0 && (
            <p className="text-sm text-gray-400 italic">No effective rules for this profile</p>
          )}
        </div>
      )}
    </div>
  )
}
