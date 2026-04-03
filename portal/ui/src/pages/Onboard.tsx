import { useState, useEffect, useMemo, useRef } from 'react'
import { api } from '../api'
import type { StandardVersion, StandardTransaction, StandardSchemaResponse } from '../api'
import { emitProfileChanged } from '../profileEvents'

interface ColumnInfo {
  name: string
  compiled_type: string
  dsl_type: string
  type_preserved?: boolean
  record_name?: string
  width?: number
}

interface RuleRow {
  segment: string
  field: string
  severity: string
  ignore_case: boolean
  numeric: boolean
  dsl_type?: string
  record_name?: string
}

interface X12Field {
  name: string
  source: string
  section: string
}

interface X12Schema {
  transaction_type: string
  input_format: string
  segments: string[]
  fields: X12Field[]
  match_key_default: Record<string, string>
}

interface WizardState {
  formatMode: 'x12' | 'other' | ''
  columns: ColumnInfo[]
  compiledYamlPath: string
  transactionType: string
  dslPath: string
  profileName: string
  rulesFile: string
  complete: boolean
  x12Schema?: X12Schema
  x12MapFile?: string
}

const STEPS_OTHER = [
  { label: 'Import & Compile', sub: 'Parse DSL schema' },
  { label: 'Register Partner', sub: 'Configure profile' },
  { label: 'Configure Rules', sub: 'Set compare rules' },
] as const

const STEPS_X12 = [
  { label: 'Select X12 Type', sub: 'Review schema' },
  { label: 'Register Partner', sub: 'Configure profile' },
  { label: 'Configure Rules', sub: 'Set compare rules' },
] as const

export default function OnboardPage({ onNavigate }: { onNavigate?: (page: string) => void }) {
  const [step, setStep] = useState(0)
  const [wizard, setWizard] = useState<WizardState>({
    formatMode: '',
    columns: [],
    compiledYamlPath: '',
    transactionType: '',
    dslPath: '',
    profileName: '',
    rulesFile: '',
    complete: false,
  })

  const updateWizard = (patch: Partial<WizardState>) =>
    setWizard(prev => ({ ...prev, ...patch }))

  const resetWizard = () => {
    setStep(0)
    setWizard({
      formatMode: '',
      columns: [],
      compiledYamlPath: '',
      transactionType: '',
      dslPath: '',
      profileName: '',
      rulesFile: '',
      complete: false,
    })
  }

  const steps = wizard.formatMode === 'x12' ? STEPS_X12 : STEPS_OTHER
  const showFormatSelector = step === 0 && !wizard.formatMode

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
          Onboard Trading Partner
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          {wizard.formatMode
            ? wizard.formatMode === 'x12'
              ? 'Select an X12 transaction type, register the partner, and configure compare rules.'
              : 'Import a DSL schema, register the partner profile, and configure compare rules.'
            : 'Choose a format to get started.'}
        </p>
      </div>

      {/* ── Format Selector (shown before step 1 if no mode chosen) ── */}
      {showFormatSelector ? (
        <FormatSelector onSelect={(mode) => updateWizard({ formatMode: mode })} />
      ) : (
        <>
          {/* ── Stepper ── */}
          <Stepper steps={steps} current={step} complete={wizard.complete} />

          {/* ── Step Content ── */}
          <div className="mt-6">
            {step === 0 && wizard.formatMode === 'x12' && (
              <StepX12Select
                wizard={wizard}
                onUpdate={updateWizard}
                onNext={() => setStep(1)}
                onChangeFormat={() => updateWizard({ formatMode: '' })}
              />
            )}
            {step === 0 && wizard.formatMode === 'other' && (
              <StepCompile
                wizard={wizard}
                onUpdate={updateWizard}
                onNext={() => setStep(1)}
                onChangeFormat={() => updateWizard({ formatMode: '' })}
              />
            )}
            {step === 1 && (
              <StepRegister
                wizard={wizard}
                onUpdate={updateWizard}
                onBack={() => setStep(0)}
                onNext={() => setStep(2)}
              />
            )}
            {step === 2 && (
              <StepRules
                wizard={wizard}
                onUpdate={updateWizard}
                onBack={() => setStep(1)}
                onNavigate={onNavigate}
                onReset={resetWizard}
              />
            )}
          </div>
        </>
      )}
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   STEPPER
   ═══════════════════════════════════════════════════════════════════════════ */

function Stepper({ steps, current, complete }: { steps: readonly { label: string; sub: string }[]; current: number; complete: boolean }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 px-8 py-5">
      <div className="flex items-center justify-between">
        {steps.map((s, i) => {
          const done = complete || i < current
          const active = i === current && !complete
          return (
            <div key={i} className="flex items-center flex-1 last:flex-none">
              {/* Node */}
              <div className="flex items-center gap-3">
                <div
                  className={`
                    w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold
                    transition-all duration-300
                    ${done
                      ? 'bg-emerald-500 text-white shadow-sm shadow-emerald-200'
                      : active
                        ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-200 ring-4 ring-indigo-100'
                        : 'bg-gray-100 text-gray-400'
                    }
                  `}
                >
                  {done ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    i + 1
                  )}
                </div>
                <div className="hidden sm:block">
                  <div className={`text-sm font-medium ${active ? 'text-indigo-700' : done ? 'text-emerald-700' : 'text-gray-400'}`}>
                    {s.label}
                  </div>
                  <div className="text-xs text-gray-400">{s.sub}</div>
                </div>
              </div>
              {/* Connector */}
              {i < steps.length - 1 && (
                <div className="flex-1 mx-4">
                  <div className={`h-0.5 rounded-full transition-colors duration-500 ${
                    i < current ? 'bg-emerald-400' : 'bg-gray-200'
                  }`} />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   FORMAT SELECTOR
   ═══════════════════════════════════════════════════════════════════════════ */

function FormatSelector({ onSelect }: { onSelect: (mode: 'x12' | 'other') => void }) {
  return (
    <div className="grid grid-cols-2 gap-6 mt-6">
      <button
        onClick={() => onSelect('x12')}
        className="group bg-white rounded-xl shadow-sm border-2 border-gray-100 p-8 text-left
                   hover:border-indigo-400 hover:shadow-md transition-all"
      >
        <div className="w-12 h-12 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center mb-4
                        group-hover:bg-indigo-600 group-hover:text-white transition-colors">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
        </div>
        <h3 className="text-lg font-bold text-gray-900 mb-1">X12 EDI</h3>
        <p className="text-sm text-gray-500">
          Onboard an X12 transaction type (810, 850, 856, etc.) using existing or uploaded mapping rules.
        </p>
      </button>

      <button
        onClick={() => onSelect('other')}
        className="group bg-white rounded-xl shadow-sm border-2 border-gray-100 p-8 text-left
                   hover:border-violet-400 hover:shadow-md transition-all"
      >
        <div className="w-12 h-12 rounded-lg bg-violet-100 text-violet-600 flex items-center justify-center mb-4
                        group-hover:bg-violet-600 group-hover:text-white transition-colors">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0112 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M10.875 12c-.621 0-1.125.504-1.125 1.125M12 10.875c-.621 0-1.125.504-1.125 1.125m0 1.5v-1.5m0 0c0-.621.504-1.125 1.125-1.125m-1.125 1.125c0 .621.504 1.125 1.125 1.125m0 0v-1.5m0 0c0-.621-.504-1.125-1.125-1.125" />
          </svg>
        </div>
        <h3 className="text-lg font-bold text-gray-900 mb-1">Flat-File / XML</h3>
        <p className="text-sm text-gray-500">
          Import a DSL schema (CSV, fixed-width) or XSD and compile it for comparison.
        </p>
      </button>
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   STEP 1 (X12) — SELECT TRANSACTION TYPE
   ═══════════════════════════════════════════════════════════════════════════ */

function StepX12Select({
  wizard,
  onUpdate,
  onNext,
  onChangeFormat,
}: {
  wizard: WizardState
  onUpdate: (p: Partial<WizardState>) => void
  onNext: () => void
  onChangeFormat: () => void
}) {
  const [standardVersions, setStandardVersions] = useState<StandardVersion[]>([])
  const [standardTransactions, setStandardTransactions] = useState<StandardTransaction[]>([])
  const [selectedStandard] = useState<string>('x12')
  const [selectedVersion, setSelectedVersion] = useState<string>('')
  const [selectedCode, setSelectedCode] = useState('')
  const [typeQuery, setTypeQuery] = useState('')
  const [comboOpen, setComboOpen] = useState(false)
  const [mode, setMode] = useState<'existing' | 'upload'>('existing')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingVersions, setLoadingVersions] = useState(true)
  const [loadingTransactions, setLoadingTransactions] = useState(false)
  const [error, setError] = useState('')
  const [schema, setSchema] = useState<X12Schema | null>(null)

  // Sample EDI validation
  const [samplePath, setSamplePath] = useState('')
  const [sampleLoading, setSampleLoading] = useState(false)
  const [sampleResult, setSampleResult] = useState<any>(null)
  const [sampleError, setSampleError] = useState('')

  // Fetch versions on mount
  useEffect(() => {
    setLoadingVersions(true)
    api.standardsCatalog()
      .then(res => {
        const x12 = res.standards.find(s => s.standard === 'x12')
        if (x12) {
          setStandardVersions(x12.versions)
          const highest = [...x12.versions].sort((a, b) => b.version.localeCompare(a.version))[0]
          if (highest) setSelectedVersion(highest.version)
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoadingVersions(false))
  }, [])

  // Fetch transactions when version changes
  useEffect(() => {
    if (!selectedVersion) return
    setLoadingTransactions(true)
    setStandardTransactions([])
    setSelectedCode('')
    setTypeQuery('')
    setSchema(null)
    api.standardsTransactions(selectedStandard, selectedVersion)
      .then(res => setStandardTransactions(res.transactions))
      .catch(e => setError(e.message))
      .finally(() => setLoadingTransactions(false))
  }, [selectedStandard, selectedVersion])

  const convertStandardSchema = (std: StandardSchemaResponse): X12Schema => {
    const segments: string[] = []
    const seen = new Set<string>()
    for (const area of std.areas) {
      for (const ref of area) {
        if (ref.ref_type === 'segment' && !seen.has(ref.name)) {
          seen.add(ref.name)
          segments.push(ref.name)
        }
        for (const child of ref.children || []) {
          if (child.ref_type === 'segment' && !seen.has(child.name)) {
            seen.add(child.name)
            segments.push(child.name)
          }
        }
      }
    }
    const fields: X12Field[] = []
    std.areas.forEach((area, areaIdx) => {
      const section = areaIdx === 0 ? 'header' : areaIdx === 1 ? 'lines' : 'summary'
      for (const ref of area) {
        const segCode = ref.ref_type === 'segment' ? ref.name : null
        if (segCode && std.segment_defs[segCode]) {
          for (const elem of std.segment_defs[segCode].elements) {
            fields.push({
              name: `${segCode}${String(elem.position).padStart(2, '0')}`,
              source: `${segCode}.${elem.position}`,
              section,
            })
          }
        }
      }
    })
    return {
      transaction_type: std.code,
      input_format: 'X12',
      segments,
      fields,
      match_key_default: std.match_key_default,
    }
  }

  const loadSchema = async () => {
    setError('')
    setSchema(null)
    setLoading(true)
    try {
      if (mode === 'existing' && selectedCode) {
        const selectedTxn = standardTransactions.find(t => t.code === selectedCode)
        if (selectedTxn?.has_mapping) {
          const res = await api.onboardX12Schema(selectedCode, selectedVersion || undefined)
          setSchema(res)
          onUpdate({ transactionType: selectedCode, x12Schema: res })
        } else {
          const stdRes = await api.standardsSchema(selectedStandard, selectedVersion, selectedCode)
          const converted = convertStandardSchema(stdRes)
          setSchema(converted)
          onUpdate({ transactionType: selectedCode, x12Schema: converted })
        }
      } else if (mode === 'upload' && uploadFile) {
        const res = await api.onboardX12UploadMap(uploadFile)
        setSchema(res.x12_schema)
        setSelectedCode(res.code)
        onUpdate({
          transactionType: res.code,
          x12Schema: res.x12_schema,
          x12MapFile: res.map_file,
        })
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const validateSample = async () => {
    if (!samplePath || !selectedCode) return
    setSampleError('')
    setSampleResult(null)
    setSampleLoading(true)
    try {
      const res = await api.onboardX12Validate(selectedCode, samplePath)
      setSampleResult(res)
    } catch (e: any) {
      setSampleError(e.message)
    } finally {
      setSampleLoading(false)
    }
  }

  const comboRef = useRef<HTMLDivElement>(null)
  const [highlightIdx, setHighlightIdx] = useState(-1)

  // Click-outside to close combobox
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (comboRef.current && !comboRef.current.contains(e.target as Node)) {
        setComboOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Filter transactions (flat sorted list — no categories for standards)
  const filteredTypes = standardTransactions.filter(t =>
    !typeQuery || t.code.includes(typeQuery) || t.name.toLowerCase().includes(typeQuery.toLowerCase())
  )

  const selectType = (code: string) => {
    setSelectedCode(code)
    const t = standardTransactions.find(x => x.code === code)
    setTypeQuery(t ? `${t.code} — ${t.name}` : code)
    setComboOpen(false)
    setSchema(null)
    setHighlightIdx(-1)
  }

  const handleComboKeyDown = (e: React.KeyboardEvent) => {
    if (!comboOpen) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') { setComboOpen(true); e.preventDefault() }
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlightIdx(i => Math.min(i + 1, filteredTypes.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlightIdx(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && highlightIdx >= 0 && highlightIdx < filteredTypes.length) {
      e.preventDefault()
      selectType(filteredTypes[highlightIdx].code)
    } else if (e.key === 'Escape') {
      setComboOpen(false)
    }
  }

  const selectedTxn = standardTransactions.find(t => t.code === selectedCode)

  const canLoad = mode === 'existing' ? (!!selectedCode && !!selectedVersion) : !!uploadFile
  const reviewed = !!schema

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center justify-between mb-4">
          <CardHeader title="Select X12 Transaction Type" />
          <button onClick={onChangeFormat} className="text-xs text-gray-400 hover:text-indigo-600 transition-colors">
            Change format
          </button>
        </div>

        {/* Mode toggle */}
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit mb-4">
          <ToggleBtn active={mode === 'existing'} onClick={() => setMode('existing')}>Existing Type</ToggleBtn>
          <ToggleBtn active={mode === 'upload'} onClick={() => setMode('upload')}>Upload New Mapping</ToggleBtn>
        </div>

        {mode === 'existing' ? (
          <div>
            {/* Version Selector */}
            <div className="mb-4">
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">X12 Version</label>
              {loadingVersions ? (
                <div className="flex items-center gap-2 text-sm text-gray-400"><Spinner /> Loading versions...</div>
              ) : (
                <select
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white max-w-xs
                             focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
                  value={selectedVersion}
                  onChange={e => setSelectedVersion(e.target.value)}
                  disabled={loadingVersions}
                >
                  {standardVersions.map(v => (
                    <option key={v.version} value={v.version}>
                      {v.version} ({v.transaction_count} transaction types)
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Transaction Type */}
            <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Transaction Type</label>
            {loadingTransactions ? (
              <div className="flex items-center gap-2 text-sm text-gray-400"><Spinner /> Loading types...</div>
            ) : (
              <div ref={comboRef} className="relative w-80">
                <div className="relative">
                  <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none"
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input
                    type="text"
                    value={typeQuery}
                    onChange={e => {
                      setTypeQuery(e.target.value)
                      setComboOpen(true)
                      setHighlightIdx(-1)
                      if (!e.target.value) { setSelectedCode('') }
                    }}
                    onFocus={() => setComboOpen(true)}
                    onKeyDown={handleComboKeyDown}
                    placeholder="Search transaction types..."
                    className="w-full border border-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm bg-white
                               focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
                  />
                </div>

                {comboOpen && filteredTypes.length > 0 && (
                  <div className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-72 overflow-auto">
                    {filteredTypes.map((t, idx) => (
                      <button
                        key={t.code}
                        onClick={() => selectType(t.code)}
                        className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 transition-colors ${
                          idx === highlightIdx ? 'bg-indigo-50' : 'hover:bg-gray-50'
                        } ${t.code === selectedCode ? 'bg-indigo-50 font-medium' : ''}`}
                      >
                        <span className="font-bold text-gray-900 w-10">{t.code}</span>
                        <span className="text-gray-600 flex-1">{t.name}</span>
                        {t.has_mapping ? (
                          <span className="text-emerald-500 text-xs" title="Custom mapping">
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400">(standard only)</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
                {comboOpen && filteredTypes.length === 0 && typeQuery && (
                  <div className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm text-gray-400">
                    No matching transaction types.
                  </div>
                )}
              </div>
            )}

            {/* Standard-only info banner */}
            {selectedTxn && !selectedTxn.has_mapping && (
              <div className="mt-3 px-4 py-2.5 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
                This transaction type is loaded from the X12 {selectedVersion} standard definition.
                Segment structure is shown below. A custom field mapping can be uploaded after onboarding.
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide">Mapping YAML File</label>
            <input type="file" accept=".yaml,.yml" className="text-sm text-gray-600"
              onChange={e => { setUploadFile(e.target.files?.[0] || null); setSchema(null) }} />
            <p className="text-xs text-gray-400">
              Upload a YAML mapping file with transaction_type, mapping (header/lines/summary), and schema sections.
            </p>
          </div>
        )}

        <div className="mt-4">
          <button
            onClick={loadSchema}
            disabled={loading || !canLoad}
            className="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-medium
                       hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-colors shadow-sm"
          >
            {loading ? (
              <span className="flex items-center gap-2"><Spinner /> Loading...</span>
            ) : mode === 'existing' ? 'Review Schema' : 'Upload & Review'}
          </button>
        </div>
      </Card>

      {error && <ErrorBanner message={error} />}

      {/* Schema review */}
      {schema && (
        <>
          <Card>
            <CardHeader title="Schema Review" badge={`${schema.fields.length} fields`} badgeColor="indigo" />
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm mb-4">
              <dt className="text-gray-500">Transaction Type</dt>
              <dd className="font-medium font-mono text-indigo-700">{schema.transaction_type}</dd>
              <dt className="text-gray-500">Input Format</dt>
              <dd className="font-medium">{schema.input_format}</dd>
              <dt className="text-gray-500">Match Key Default</dt>
              <dd className="font-mono text-xs">
                {schema.match_key_default.segment}.{schema.match_key_default.field}
              </dd>
              <dt className="text-gray-500">Required Segments</dt>
              <dd className="font-mono text-xs">{schema.segments.join(', ')}</dd>
            </dl>

            <div className="overflow-auto max-h-72 rounded-lg border border-gray-100">
              <table className="w-full text-sm text-left">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <Th>Section</Th>
                    <Th>Field Name</Th>
                    <Th>Source (Segment.Element)</Th>
                  </tr>
                </thead>
                <tbody>
                  {schema.fields.map((f, i) => (
                    <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                      <td className="px-3 py-1.5">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                          f.section === 'header' ? 'bg-blue-100 text-blue-700'
                            : f.section === 'lines' ? 'bg-emerald-100 text-emerald-700'
                            : 'bg-amber-100 text-amber-700'
                        }`}>
                          {f.section}
                        </span>
                      </td>
                      <td className="px-3 py-1.5 font-mono text-xs font-medium text-gray-800">{f.name}</td>
                      <td className="px-3 py-1.5 font-mono text-xs text-gray-500">{f.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Optional sample validation */}
          <Card>
            <CardHeader title="Sample EDI Validation" badge="Optional" badgeColor="amber" />
            <div className="flex gap-3 items-end">
              <div className="flex-1">
                <Input label="Sample EDI File Path" value={samplePath} onChange={setSamplePath}
                  placeholder="testingData/sample_810.edi" />
              </div>
              <button
                onClick={validateSample}
                disabled={sampleLoading || !samplePath}
                className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg text-sm font-medium
                           hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed
                           transition-colors"
              >
                {sampleLoading ? <Spinner /> : 'Validate'}
              </button>
            </div>
            {sampleError && <div className="mt-2"><ErrorBanner message={sampleError} /></div>}
            {sampleResult && (
              <div className="mt-3">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                    {sampleResult.segment_count} segments parsed
                  </span>
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                    ST01: {sampleResult.transaction_type}
                  </span>
                </div>
                <div className="overflow-auto max-h-48 rounded-lg border border-gray-100 text-xs">
                  <table className="w-full text-left">
                    <thead className="bg-gray-50 sticky top-0">
                      <tr>
                        <th className="px-2 py-1 font-semibold text-gray-500">Segment</th>
                        <th className="px-2 py-1 font-semibold text-gray-500">Fields</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sampleResult.segments.map((seg: any, i: number) => (
                        <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                          <td className="px-2 py-1 font-mono font-medium text-indigo-700">{seg.segment}</td>
                          <td className="px-2 py-1 font-mono text-gray-500">
                            {seg.fields.map((f: any) => `${f.name}=${f.content}`).join(' | ')}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </Card>
        </>
      )}

      {/* Navigation */}
      <div className="flex justify-end pt-2">
        <button
          onClick={onNext}
          disabled={!reviewed}
          className="bg-indigo-600 text-white px-6 py-2 rounded-lg text-sm font-medium
                     hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed
                     transition-colors shadow-sm flex items-center gap-2"
        >
          Next: Register Partner
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   STEP 1 (OTHER) — IMPORT & COMPILE
   ═══════════════════════════════════════════════════════════════════════════ */

function StepCompile({
  wizard,
  onUpdate,
  onNext,
  onChangeFormat,
}: {
  wizard: WizardState
  onUpdate: (p: Partial<WizardState>) => void
  onNext: () => void
  onChangeFormat: () => void
}) {
  const [mode, setMode] = useState<'path' | 'upload'>('path')
  const [dslPath, setDslPath] = useState(wizard.dslPath || '')
  const [samplePath, setSamplePath] = useState('')
  const [dslFile, setDslFile] = useState<File | null>(null)
  const [sampleFile, setSampleFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<any>(null)
  const compiled = !!result
  const [columnSearch, setColumnSearch] = useState('')
  const [collapsedRecords, setCollapsedRecords] = useState<Set<string>>(new Set())

  const groupedColumns = useMemo(() => {
    const groups = new Map<string, ColumnInfo[]>()
    const cols = result?.columns || []
    const search = columnSearch.toLowerCase()

    for (const col of cols) {
      if (search && !col.name.toLowerCase().includes(search)) continue
      const key = col.record_name || '(ungrouped)'
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(col)
    }
    return groups
  }, [result?.columns, columnSearch])

  const toggleRecord = (name: string) => {
    setCollapsedRecords(prev => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
  }

  const runCompile = async () => {
    setError('')
    setResult(null)
    setLoading(true)
    try {
      let res: any
      if (mode === 'upload' && dslFile) {
        res = await api.validateUpload(dslFile, sampleFile || undefined)
      } else {
        res = await api.validate(dslPath, samplePath || undefined)
      }
      setResult(res)
      onUpdate({
        columns: res.columns || [],
        compiledYamlPath: res.compiled_yaml_path || '',
        transactionType: res.transaction_type || '',
        dslPath: mode === 'path' ? dslPath : (dslFile?.name || ''),
      })
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center justify-between mb-4">
          <CardHeader title="Import DSL Schema" />
          <button onClick={onChangeFormat} className="text-xs text-gray-400 hover:text-indigo-600 transition-colors">
            Change format
          </button>
        </div>

        {/* Mode toggle */}
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit mb-4">
          <ToggleBtn active={mode === 'path'} onClick={() => setMode('path')}>Server Path</ToggleBtn>
          <ToggleBtn active={mode === 'upload'} onClick={() => setMode('upload')}>Upload File</ToggleBtn>
        </div>

        {mode === 'path' ? (
          <div className="space-y-2">
            <Input label="DSL File Path" value={dslPath} onChange={setDslPath}
              placeholder="testingData/Batch1/bevager810FF.txt" />
            <Input label="Sample File (optional)" value={samplePath} onChange={setSamplePath}
              placeholder="path/to/sample.csv" />
          </div>
        ) : (
          <div className="space-y-2">
            <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide">DSL File</label>
            <input type="file" className="text-sm text-gray-600" onChange={e => setDslFile(e.target.files?.[0] || null)} />
            <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide pt-1">Sample File (optional)</label>
            <input type="file" className="text-sm text-gray-600" onChange={e => setSampleFile(e.target.files?.[0] || null)} />
          </div>
        )}

        <div className="mt-4">
          <button
            onClick={runCompile}
            disabled={loading || (mode === 'path' ? !dslPath : !dslFile)}
            className="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-medium
                       hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-colors shadow-sm"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <Spinner /> Compiling...
              </span>
            ) : 'Compile'}
          </button>
        </div>
      </Card>

      {error && <ErrorBanner message={error} />}

      {result && (
        <>
          {/* Summary */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-gray-800 uppercase tracking-wide">Compilation Result</h2>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                  result.columns?.some((c: any) => c.width)
                    ? 'bg-violet-100 text-violet-700'
                    : 'bg-blue-100 text-blue-700'
                }`}>
                  {result.columns?.some((c: any) => c.width) ? 'Fixed-Width' : 'Delimited'}
                </span>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                  {result.columns?.length || 0} columns
                </span>
                {new Set((result?.columns || []).map((c: any) => c.record_name).filter(Boolean)).size > 1 && (
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">
                    {new Set((result?.columns || []).map((c: any) => c.record_name).filter(Boolean)).size} records
                  </span>
                )}
              </div>
            </div>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <dt className="text-gray-500">Transaction Type</dt>
              <dd className="font-medium font-mono text-indigo-700">{result.transaction_type}</dd>
              <dt className="text-gray-500">Compiled Path</dt>
              <dd className="font-mono text-xs truncate">{result.compiled_yaml_path}</dd>
              <dt className="text-gray-500">Columns</dt>
              <dd className="font-medium">{result.columns?.length}</dd>
            </dl>
          </Card>

          {/* Type warnings */}
          {result.type_warnings?.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-amber-800 mb-2">
                Type Warnings ({result.type_warnings.length})
              </h3>
              <ul className="text-sm text-amber-700 space-y-1">
                {result.type_warnings.map((tw: any, i: number) => (
                  <li key={i}>
                    <span className="font-mono font-medium">{tw.field_name}</span>
                    <span className="text-amber-500 mx-1">({tw.record_name})</span>
                    {tw.dsl_type} &rarr; {tw.compiled_type}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Columns table */}
          <Card>
            <CardHeader title="Schema Columns" />
            <input
              type="text"
              placeholder="Search fields..."
              value={columnSearch}
              onChange={e => setColumnSearch(e.target.value)}
              className="w-full px-3 py-1.5 border border-gray-200 rounded text-sm mb-3"
            />
            <div className="overflow-auto max-h-80 rounded-lg border border-gray-100">
              {Array.from(groupedColumns.entries()).map(([recordName, cols]) => (
                <div key={recordName} className="mb-2">
                  {groupedColumns.size > 1 && (
                    <button
                      onClick={() => toggleRecord(recordName)}
                      className="w-full flex items-center justify-between px-3 py-2 bg-indigo-50 rounded-t text-sm font-semibold text-indigo-800 hover:bg-indigo-100 transition-colors"
                    >
                      <span>{recordName} <span className="font-normal text-indigo-500">({cols.length} fields)</span></span>
                      <span className="text-indigo-400">{collapsedRecords.has(recordName) ? '\u25B6' : '\u25BC'}</span>
                    </button>
                  )}
                  {!collapsedRecords.has(recordName) && (
                    <table className="w-full text-sm text-left">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          <Th>Field Name</Th>
                          <Th>DSL Type</Th>
                          <Th>Compiled Type</Th>
                          <Th align="center">Width</Th>
                          <Th align="center">Preserved</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {cols.map((c, i) => (
                          <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                            <td className="px-3 py-1.5 font-mono text-xs font-medium text-gray-800">{c.name}</td>
                            <td className="px-3 py-1.5 text-gray-500">{c.dsl_type || '\u2014'}</td>
                            <td className="px-3 py-1.5 text-gray-500">{c.compiled_type}</td>
                            <td className="px-3 py-1.5 text-center font-mono text-xs text-gray-500">{c.width || '\u2014'}</td>
                            <td className="px-3 py-1.5 text-center">
                              {c.type_preserved
                                ? <span className="text-emerald-500 font-bold">&#10003;</span>
                                : <span className="text-red-400 font-bold">&#10007;</span>
                              }
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </>
      )}

      {/* Navigation */}
      <div className="flex justify-end pt-2">
        <button
          onClick={onNext}
          disabled={!compiled}
          className="bg-indigo-600 text-white px-6 py-2 rounded-lg text-sm font-medium
                     hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed
                     transition-colors shadow-sm flex items-center gap-2"
        >
          Next: Register Partner
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   STEP 2 — REGISTER PARTNER
   ═══════════════════════════════════════════════════════════════════════════ */

function StepRegister({
  wizard,
  onUpdate,
  onBack,
  onNext,
}: {
  wizard: WizardState
  onUpdate: (p: Partial<WizardState>) => void
  onBack: () => void
  onNext: () => void
}) {
  const suggestProfileName = (path: string) => {
    const base = path.replace(/\\/g, '/').split('/').pop()?.replace(/\.[^.]+$/, '') || ''
    return base.replace(/([A-Z])/g, '_$1').replace(/^_/, '').toLowerCase().replace(/[^a-z0-9_]/g, '')
  }

  const isX12 = wizard.formatMode === 'x12'
  const [profileName, setProfileName] = useState(wizard.profileName || suggestProfileName(wizard.dslPath || wizard.transactionType))
  const [tradingPartner, setTradingPartner] = useState('')
  const [transactionType, setTransactionType] = useState(wizard.transactionType)
  const [description, setDescription] = useState('')
  const [inboundDir, setInboundDir] = useState('')
  const [matchKeyType, setMatchKeyType] = useState<'json' | 'x12'>(isX12 ? 'x12' : 'json')
  const [jsonField, setJsonField] = useState(wizard.columns[0]?.name || '')
  const [x12Segment, setX12Segment] = useState(isX12 ? (wizard.x12Schema?.match_key_default?.segment || '') : '')
  const [x12Field, setX12Field] = useState(isX12 ? (wizard.x12Schema?.match_key_default?.field || '') : '')
  const [splitKey, setSplitKey] = useState<string | null>(null)
  const [splitBoundary, setSplitBoundary] = useState<string | null>(null)
  const [splitAutoDetected, setSplitAutoDetected] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  // Auto-detect split key from compiled schema
  useEffect(() => {
    if (!wizard.compiledYamlPath) return
    api.onboardSplitSuggestion(wizard.compiledYamlPath).then(res => {
      if (res.split_key) {
        setSplitKey(res.split_key)
        setSplitBoundary(res.boundary_record)
        setSplitAutoDetected(true)
      }
    }).catch(() => { /* no split suggestion available */ })
  }, [wizard.compiledYamlPath])

  const profileNameValid = /^[a-z0-9_]+$/.test(profileName)
  const canRegister = profileNameValid && tradingPartner && transactionType && !success

  const register = async () => {
    setError('')
    setLoading(true)
    try {
      const matchKey: Record<string, string> = matchKeyType === 'json'
        ? { json_path: `header.${jsonField}` }
        : { segment: x12Segment, field: x12Field }

      const res = await api.onboardRegister({
        profile_name: profileName,
        trading_partner: tradingPartner,
        transaction_type: transactionType,
        description,
        source_dsl: isX12 ? (wizard.x12MapFile || '') : wizard.dslPath,
        compiled_output: isX12 ? (wizard.x12MapFile || '') : wizard.compiledYamlPath,
        inbound_dir: inboundDir,
        match_key: matchKey,
        segment_qualifiers: {},
        split_config: splitKey ? { split_key: splitKey, ...(splitBoundary ? { boundary_record: splitBoundary } : {}) } : null,
      })
      onUpdate({ profileName: res.profile_name, rulesFile: res.rules_file })
      setSuccess(true)
    } catch (e: any) {
      if (e.message.includes('409')) {
        setError(`Profile "${profileName}" already exists. Choose a different name.`)
      } else {
        setError(e.message)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Register Trading Partner" />

        <p className="text-xs text-gray-400 mb-3"><span className="text-red-500">*</span> Required</p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Input label="Profile Name" value={profileName}
              onChange={v => setProfileName(v.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
              placeholder="bevager_810" required />
            {profileName && !profileNameValid && (
              <p className="text-xs text-red-500 mt-1">Lowercase letters, numbers, underscores only</p>
            )}
          </div>
          <Input label="Trading Partner" value={tradingPartner} onChange={setTradingPartner}
            placeholder="Bevager" required />
          <Input label="Transaction Type" value={transactionType} onChange={setTransactionType}
            placeholder="810" required />
          <Input label="Description" value={description} onChange={setDescription}
            placeholder="Bevager 810 Invoice flat file comparison" />
          <div className="col-span-2">
            <Input label="Inbound Directory" value={inboundDir} onChange={setInboundDir}
              placeholder="./testingData/Batch1/testSample-FlatFile-Target" />
          </div>
        </div>

        {/* Match key */}
        <div className="mt-5 pt-4 border-t border-gray-100">
          <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Match Key</label>
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit mb-3">
            <ToggleBtn active={matchKeyType === 'json'} onClick={() => setMatchKeyType('json')}>JSON Path</ToggleBtn>
            <ToggleBtn active={matchKeyType === 'x12'} onClick={() => setMatchKeyType('x12')}>X12 Segment/Field</ToggleBtn>
          </div>

          {matchKeyType === 'json' ? (
            <div>
              <label className="block text-xs text-gray-500 mb-1">Field (header.&lt;field&gt;)</label>
              <select
                value={jsonField}
                onChange={e => setJsonField(e.target.value)}
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white w-64
                           focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
              >
                {wizard.columns.map(c => (
                  <option key={c.name} value={c.name}>header.{c.name}</option>
                ))}
              </select>
            </div>
          ) : (
            <div className="flex gap-3">
              <Input label="Segment" value={x12Segment} onChange={setX12Segment} placeholder="BIG" />
              <Input label="Field" value={x12Field} onChange={setX12Field} placeholder="BIG02" />
            </div>
          )}
        </div>

        {/* Split key (flat-file only — X12 transactions are already split by ST/SE envelope) */}
        {!isX12 && (
          <div className="mt-5 pt-4 border-t border-gray-100">
            <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
              Transaction Split Key
              <span className="ml-2 text-gray-400 normal-case font-normal" title="Field that identifies individual transactions in batch files. Records without this field will be grouped as file-level metadata.">(?)</span>
            </label>
            {splitAutoDetected ? (
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm bg-emerald-50 text-emerald-700 px-3 py-1.5 rounded-lg border border-emerald-200">
                  {splitKey}
                </span>
                <span className="text-xs text-emerald-600">(auto-detected from schema, boundary: {splitBoundary})</span>
              </div>
            ) : (
              <div>
                <select
                  value={splitKey || ''}
                  onChange={e => setSplitKey(e.target.value || null)}
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white w-64
                             focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
                >
                  <option value="">None (no batch splitting)</option>
                  {wizard.columns.map(c => (
                    <option key={c.name} value={c.name}>{c.name}</option>
                  ))}
                </select>
                <p className="text-xs text-gray-400 mt-1">Optional: select the field that identifies individual transactions in batch files</p>
              </div>
            )}
          </div>
        )}

        <div className="mt-5">
          <button
            onClick={register}
            disabled={!canRegister || loading}
            className="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-medium
                       hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-colors shadow-sm"
          >
            {loading ? (
              <span className="flex items-center gap-2"><Spinner /> Registering...</span>
            ) : 'Register'}
          </button>
        </div>
      </Card>

      {error && <ErrorBanner message={error} />}

      {success && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-start gap-3">
          <div className="w-6 h-6 rounded-full bg-emerald-500 text-white flex items-center justify-center flex-shrink-0 mt-0.5">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-emerald-800">Partner registered successfully</p>
            <p className="text-sm text-emerald-600 mt-0.5">
              Profile <span className="font-mono font-medium">{profileName}</span> created.
              Rules file: <span className="font-mono text-xs">{wizard.rulesFile}</span>
            </p>
          </div>
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between pt-2">
        <button onClick={onBack} className="text-gray-500 hover:text-gray-700 text-sm flex items-center gap-1 transition-colors">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>
        <button
          onClick={onNext}
          disabled={!success}
          className="bg-indigo-600 text-white px-6 py-2 rounded-lg text-sm font-medium
                     hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed
                     transition-colors shadow-sm flex items-center gap-2"
        >
          Next: Configure Rules
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
        {!success && (
          <p className="text-xs text-gray-400 mt-1 text-right">Register your partner above before proceeding</p>
        )}
      </div>
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   STEP 3 — CONFIGURE RULES
   ═══════════════════════════════════════════════════════════════════════════ */

function StepRules({
  wizard,
  onUpdate,
  onBack,
  onNavigate,
  onReset,
}: {
  wizard: WizardState
  onUpdate: (p: Partial<WizardState>) => void
  onBack: () => void
  onNavigate?: (page: string) => void
  onReset: () => void
}) {
  const [rules, setRules] = useState<RuleRow[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [ruleSearch, setRuleSearch] = useState('')
  const [collapsedRuleRecords, setCollapsedRuleRecords] = useState<Set<string>>(new Set())

  // Load template on mount — X12 seeds from schema fields, flat-file from compiled YAML
  useEffect(() => {
    if (wizard.formatMode === 'x12' && wizard.x12Schema) {
      const rows: RuleRow[] = wizard.x12Schema.fields.map(f => {
        const seg = f.source.split('.')[0] || '*'
        return {
          segment: seg,
          field: f.name,
          severity: 'hard',
          ignore_case: false,
          numeric: false,
          dsl_type: f.source,
          record_name: f.section,
        }
      })
      // Add catch-all
      rows.push({ segment: '*', field: '*', severity: 'hard', ignore_case: false, numeric: false, record_name: '' })
      setRules(rows)
      setLoading(false)
      return
    }
    if (!wizard.compiledYamlPath) return
    setLoading(true)
    api.onboardRulesTemplate(wizard.compiledYamlPath)
      .then(data => {
        const rows: RuleRow[] = data.classification.map((r: any) => {
          const col = wizard.columns.find(c => c.name === r.field)
          return { ...r, dsl_type: col?.dsl_type || col?.compiled_type || '', record_name: r.record_name || col?.record_name || '' }
        })
        setRules(rows)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [wizard.compiledYamlPath, wizard.formatMode, wizard.x12Schema])

  const updateRule = (idx: number, patch: Partial<RuleRow>) => {
    setRules(prev => prev.map((r, i) => i === idx ? { ...r, ...patch } : r))
  }

  const groupedRules: {
    groups: Map<string, { rules: RuleRow[]; indices: number[] }>
    catchAll: { rule: RuleRow; index: number } | null
  } = useMemo(() => {
    const groups = new Map<string, { rules: RuleRow[]; indices: number[] }>()
    const search = ruleSearch.toLowerCase()
    let catchAll: { rule: RuleRow; index: number } | null = null

    rules.forEach((r, i) => {
      if (r.segment === '*' && r.field === '*') {
        catchAll = { rule: r, index: i }
        return
      }
      if (search && !r.field.toLowerCase().includes(search)) return

      const key = r.record_name || '(ungrouped)'
      if (!groups.has(key)) groups.set(key, { rules: [], indices: [] })
      const g = groups.get(key)!
      g.rules.push(r)
      g.indices.push(i)
    })
    return { groups, catchAll }
  }, [rules, ruleSearch])

  const setRecordSeverity = (recordName: string, severity: string) => {
    setRules(prev => prev.map(r =>
      r.record_name === recordName && !(r.segment === '*' && r.field === '*')
        ? { ...r, severity }
        : r
    ))
  }

  const toggleRuleRecord = (name: string) => {
    setCollapsedRuleRecords(prev => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
  }

  const saveRules = async () => {
    setError('')
    setSaving(true)
    try {
      const payload = {
        classification: rules.map(({ dsl_type, record_name, ...r }) => r),
        ignore: [],
      }
      await api.compareUpdateRules(wizard.profileName, payload)
      onUpdate({ complete: true })
      emitProfileChanged({ action: 'created', profileName: wizard.profileName })
      setSaved(true)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <Card>
        <div className="flex items-center justify-center py-12 text-gray-400 gap-2">
          <Spinner /> Loading rules template...
        </div>
      </Card>
    )
  }

  if (saved) {
    return (
      <div className="space-y-4">
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-6 text-center">
          <div className="w-14 h-14 rounded-full bg-emerald-500 text-white flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-lg font-bold text-emerald-900">Trading Partner Onboarded</h2>
          <p className="text-sm text-emerald-700 mt-1 mb-4">
            All configuration saved and ready for comparison runs.
          </p>
          <dl className="text-sm text-left max-w-md mx-auto grid grid-cols-2 gap-x-4 gap-y-1 mb-6">
            <dt className="text-emerald-600">Profile</dt>
            <dd className="font-mono font-medium text-emerald-900">{wizard.profileName}</dd>
            <dt className="text-emerald-600">Transaction</dt>
            <dd className="font-medium text-emerald-900">{wizard.transactionType}</dd>
            <dt className="text-emerald-600">Rules File</dt>
            <dd className="font-mono text-xs text-emerald-800 truncate">{wizard.rulesFile}</dd>
            <dt className="text-emerald-600">Columns</dt>
            <dd className="font-medium text-emerald-900">{wizard.columns.length}</dd>
          </dl>
          <div className="flex gap-3 justify-center">
            {onNavigate && (
              <button
                onClick={() => onNavigate('compare')}
                className="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-medium
                           hover:bg-indigo-700 transition-colors shadow-sm"
              >
                Go to Compare
              </button>
            )}
            <button
              onClick={onReset}
              className="bg-white text-gray-700 border border-gray-200 px-5 py-2 rounded-lg text-sm font-medium
                         hover:bg-gray-50 transition-colors"
            >
              Onboard Another
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Compare Rules" badge={`${rules.length} rules`} badgeColor="indigo" />

        <div className="mb-4 px-4 py-2.5 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-700">
          These are partner-specific rules. Universal and transaction-type rules (if configured)
          will also apply automatically. Manage rule tiers in the Rules page.
        </div>

        <input
          type="text"
          placeholder="Search rules..."
          value={ruleSearch}
          onChange={e => setRuleSearch(e.target.value)}
          className="w-full px-3 py-1.5 border border-gray-200 rounded text-sm mb-3"
        />

        <div className="overflow-auto max-h-[28rem] rounded-lg border border-gray-100">
          {Array.from(groupedRules.groups.entries()).map(([recordName, { rules: recordRules, indices }]) => (
            <div key={recordName} className="mb-2">
              {groupedRules.groups.size > 1 && (
                <div className="flex items-center justify-between px-3 py-2 bg-indigo-50 rounded-t">
                  <button
                    onClick={() => toggleRuleRecord(recordName)}
                    className="flex items-center gap-2 text-sm font-semibold text-indigo-800 hover:text-indigo-900"
                  >
                    <span>{collapsedRuleRecords.has(recordName) ? '\u25B6' : '\u25BC'}</span>
                    <span>{recordName} <span className="font-normal text-indigo-500">({recordRules.length} rules)</span></span>
                  </button>
                  <select
                    className="text-xs border border-indigo-200 rounded px-2 py-1 bg-white text-indigo-700"
                    value=""
                    onChange={e => { if (e.target.value) setRecordSeverity(recordName, e.target.value) }}
                  >
                    <option value="">Set all...</option>
                    <option value="hard">hard</option>
                    <option value="soft">soft</option>
                    <option value="ignore">ignore</option>
                  </select>
                </div>
              )}
              {!collapsedRuleRecords.has(recordName) && (
                <table className="w-full text-sm text-left">
                  <thead className="bg-gray-50 sticky top-0 z-10">
                    <tr>
                      <Th>Field</Th>
                      <Th>DSL Type</Th>
                      <Th>Severity</Th>
                      <Th align="center">Numeric</Th>
                      <Th align="center">Ignore Case</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {recordRules.map((r, j) => {
                      const idx = indices[j]
                      return (
                        <tr key={idx} className={j % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                          <td className="px-3 py-1.5 font-mono text-xs font-medium text-gray-800">{r.field}</td>
                          <td className="px-3 py-1.5 text-gray-500 text-xs">{r.dsl_type}</td>
                          <td className="px-3 py-1.5">
                            <select
                              value={r.severity}
                              onChange={e => updateRule(idx, { severity: e.target.value })}
                              className={`text-xs border rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-indigo-200
                                ${r.severity === 'hard' ? 'border-red-200 bg-red-50 text-red-700'
                                  : r.severity === 'soft' ? 'border-amber-200 bg-amber-50 text-amber-700'
                                  : 'border-gray-200 bg-gray-50 text-gray-500'
                                }`}
                            >
                              <option value="hard">hard</option>
                              <option value="soft">soft</option>
                              <option value="ignore">ignore</option>
                            </select>
                          </td>
                          <td className="px-3 py-1.5 text-center">
                            <input type="checkbox" checked={r.numeric} onChange={e => updateRule(idx, { numeric: e.target.checked })}
                              className="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" />
                          </td>
                          <td className="px-3 py-1.5 text-center">
                            <input type="checkbox" checked={r.ignore_case} onChange={e => updateRule(idx, { ignore_case: e.target.checked })}
                              className="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" />
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          ))}

          {/* Catch-all rule */}
          {groupedRules.catchAll && (
            <div className="mt-4 border-t border-gray-200 pt-3">
              <table className="w-full text-sm text-left">
                <tbody>
                  <tr className="bg-gray-50/50">
                    <td className="px-3 py-1.5 font-mono text-xs text-gray-400 italic">* / * (catch-all)</td>
                    <td className="px-3 py-1.5"></td>
                    <td className="px-3 py-1.5">
                      <select value={groupedRules.catchAll.rule.severity}
                        onChange={e => updateRule(groupedRules.catchAll!.index, { severity: e.target.value })}
                        className="text-xs border border-gray-200 rounded px-2 py-1">
                        <option value="hard">hard</option>
                        <option value="soft">soft</option>
                        <option value="ignore">ignore</option>
                      </select>
                    </td>
                    <td className="px-3 py-1.5 text-center">
                      <input type="checkbox" checked={groupedRules.catchAll.rule.numeric}
                        onChange={e => updateRule(groupedRules.catchAll!.index, { numeric: e.target.checked })} />
                    </td>
                    <td className="px-3 py-1.5 text-center">
                      <input type="checkbox" checked={groupedRules.catchAll.rule.ignore_case}
                        onChange={e => updateRule(groupedRules.catchAll!.index, { ignore_case: e.target.checked })} />
                    </td>
                  </tr>
                </tbody>
              </table>
              <p className="text-xs text-gray-400 mt-1 px-3">Applies to any field not matched by a specific rule above.</p>
            </div>
          )}
        </div>

        <div className="mt-4">
          <button
            onClick={saveRules}
            disabled={saving}
            className="bg-emerald-600 text-white px-5 py-2 rounded-lg text-sm font-medium
                       hover:bg-emerald-700 disabled:opacity-40 transition-colors shadow-sm"
          >
            {saving ? (
              <span className="flex items-center gap-2"><Spinner /> Saving...</span>
            ) : 'Save Rules'}
          </button>
        </div>
      </Card>

      {error && <ErrorBanner message={error} />}

      <div className="flex justify-between pt-2">
        <button onClick={onBack} className="text-gray-500 hover:text-gray-700 text-sm flex items-center gap-1 transition-colors">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>
      </div>
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   SHARED PRIMITIVES
   ═══════════════════════════════════════════════════════════════════════════ */

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      {children}
    </div>
  )
}

function CardHeader({ title, badge, badgeColor }: { title: string; badge?: string; badgeColor?: string }) {
  const colors: Record<string, string> = {
    emerald: 'bg-emerald-100 text-emerald-700',
    indigo: 'bg-indigo-100 text-indigo-700',
    amber: 'bg-amber-100 text-amber-700',
  }
  return (
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-sm font-semibold text-gray-800 uppercase tracking-wide">{title}</h2>
      {badge && (
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${colors[badgeColor || 'indigo']}`}>
          {badge}
        </span>
      )}
    </div>
  )
}

function Input({ label, value, onChange, placeholder, required }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; required?: boolean
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white
                   placeholder:text-gray-300
                   focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400
                   transition-shadow"
      />
    </div>
  )
}

function ToggleBtn({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 rounded-md text-xs font-medium transition-all
        ${active
          ? 'bg-white text-indigo-700 shadow-sm'
          : 'text-gray-500 hover:text-gray-700'
        }`}
    >
      {children}
    </button>
  )
}

function Th({ children, align }: { children: React.ReactNode; align?: string }) {
  return (
    <th className={`px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide ${align === 'center' ? 'text-center' : ''}`}>
      {children}
    </th>
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700 flex items-start gap-2">
      <svg className="w-4 h-4 mt-0.5 flex-shrink-0 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      {message}
    </div>
  )
}

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}
