import { useState, useEffect } from 'react'
import { api } from '../api'

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
}

interface WizardState {
  columns: ColumnInfo[]
  compiledYamlPath: string
  transactionType: string
  dslPath: string
  profileName: string
  rulesFile: string
  complete: boolean
}

const STEPS = [
  { label: 'Import & Compile', sub: 'Parse DSL schema' },
  { label: 'Register Partner', sub: 'Configure profile' },
  { label: 'Configure Rules', sub: 'Set compare rules' },
] as const

export default function OnboardPage({ onNavigate }: { onNavigate?: (page: string) => void }) {
  const [step, setStep] = useState(0)
  const [wizard, setWizard] = useState<WizardState>({
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
      columns: [],
      compiledYamlPath: '',
      transactionType: '',
      dslPath: '',
      profileName: '',
      rulesFile: '',
      complete: false,
    })
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
          Onboard Trading Partner
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Import a DSL schema, register the partner profile, and configure compare rules.
        </p>
      </div>

      {/* ── Stepper ── */}
      <Stepper current={step} complete={wizard.complete} />

      {/* ── Step Content ── */}
      <div className="mt-6">
        {step === 0 && (
          <StepCompile
            wizard={wizard}
            onUpdate={updateWizard}
            onNext={() => setStep(1)}
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
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   STEPPER
   ═══════════════════════════════════════════════════════════════════════════ */

function Stepper({ current, complete }: { current: number; complete: boolean }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 px-8 py-5">
      <div className="flex items-center justify-between">
        {STEPS.map((s, i) => {
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
              {i < STEPS.length - 1 && (
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
   STEP 1 — IMPORT & COMPILE
   ═══════════════════════════════════════════════════════════════════════════ */

function StepCompile({
  wizard,
  onUpdate,
  onNext,
}: {
  wizard: WizardState
  onUpdate: (p: Partial<WizardState>) => void
  onNext: () => void
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
        <CardHeader title="Import DSL Schema" />

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
            <div className="overflow-auto max-h-80 rounded-lg border border-gray-100">
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
                  {result.columns?.map((c: any, i: number) => (
                    <tr key={i} className={`border-t border-gray-50 ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'} hover:bg-indigo-50/40 transition-colors`}>
                      <td className="px-3 py-1.5 font-mono text-xs font-medium text-gray-800">{c.name}</td>
                      <td className="px-3 py-1.5 text-gray-500">{c.dsl_type || '\u2014'}</td>
                      <td className="px-3 py-1.5 text-gray-500">{c.compiled_type}</td>
                      <td className="px-3 py-1.5 text-center font-mono text-xs text-gray-500">
                        {c.width || '\u2014'}
                      </td>
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

  const [profileName, setProfileName] = useState(wizard.profileName || suggestProfileName(wizard.dslPath))
  const [tradingPartner, setTradingPartner] = useState('')
  const [transactionType, setTransactionType] = useState(wizard.transactionType)
  const [description, setDescription] = useState('')
  const [inboundDir, setInboundDir] = useState('')
  const [matchKeyType, setMatchKeyType] = useState<'json' | 'x12'>('json')
  const [jsonField, setJsonField] = useState(wizard.columns[0]?.name || '')
  const [x12Segment, setX12Segment] = useState('')
  const [x12Field, setX12Field] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const profileNameValid = /^[a-z0-9_]+$/.test(profileName)
  const canRegister = profileNameValid && tradingPartner && transactionType && !success

  const register = async () => {
    setError('')
    setLoading(true)
    try {
      const matchKey = matchKeyType === 'json'
        ? { json_path: `header.${jsonField}` }
        : { segment: x12Segment, field: x12Field }

      const res = await api.onboardRegister({
        profile_name: profileName,
        trading_partner: tradingPartner,
        transaction_type: transactionType,
        description,
        source_dsl: wizard.dslPath,
        compiled_output: wizard.compiledYamlPath,
        inbound_dir: inboundDir,
        match_key: matchKey,
        segment_qualifiers: {},
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

        <div className="grid grid-cols-2 gap-4">
          <div>
            <Input label="Profile Name" value={profileName}
              onChange={v => setProfileName(v.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
              placeholder="bevager_810" />
            {profileName && !profileNameValid && (
              <p className="text-xs text-red-500 mt-1">Lowercase letters, numbers, underscores only</p>
            )}
          </div>
          <Input label="Trading Partner" value={tradingPartner} onChange={setTradingPartner}
            placeholder="Bevager" />
          <Input label="Transaction Type" value={transactionType} onChange={setTransactionType}
            placeholder="810" />
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

  // Load template on mount
  useEffect(() => {
    if (!wizard.compiledYamlPath) return
    setLoading(true)
    api.onboardRulesTemplate(wizard.compiledYamlPath)
      .then(data => {
        const rows: RuleRow[] = data.classification.map(r => {
          const col = wizard.columns.find(c => c.name === r.field)
          return { ...r, dsl_type: col?.dsl_type || col?.compiled_type || '' }
        })
        setRules(rows)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [wizard.compiledYamlPath])

  const updateRule = (idx: number, patch: Partial<RuleRow>) => {
    setRules(prev => prev.map((r, i) => i === idx ? { ...r, ...patch } : r))
  }

  const saveRules = async () => {
    setError('')
    setSaving(true)
    try {
      const payload = {
        classification: rules.map(({ dsl_type, ...r }) => r),
        ignore: [],
      }
      await api.compareUpdateRules(wizard.profileName, payload)
      onUpdate({ complete: true })
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

        <div className="overflow-auto max-h-[28rem] rounded-lg border border-gray-100">
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
              {rules.map((r, i) => {
                const isCatchAll = r.segment === '*' && r.field === '*'
                return (
                  <tr
                    key={i}
                    className={`border-t border-gray-50 transition-colors hover:bg-indigo-50/40
                      ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}
                      ${isCatchAll ? 'bg-gray-100/60' : ''}
                    `}
                  >
                    <td className="px-3 py-1.5 font-mono text-xs font-medium text-gray-800">
                      {isCatchAll ? (
                        <span className="text-gray-400 italic">* / * (catch-all)</span>
                      ) : r.field}
                    </td>
                    <td className="px-3 py-1.5 text-gray-500 text-xs">{isCatchAll ? '' : r.dsl_type}</td>
                    <td className="px-3 py-1.5">
                      <select
                        value={r.severity}
                        onChange={e => updateRule(i, { severity: e.target.value })}
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
                      <input
                        type="checkbox"
                        checked={r.numeric}
                        onChange={e => updateRule(i, { numeric: e.target.checked })}
                        className="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                    </td>
                    <td className="px-3 py-1.5 text-center">
                      <input
                        type="checkbox"
                        checked={r.ignore_case}
                        onChange={e => updateRule(i, { ignore_case: e.target.checked })}
                        className="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
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

function Input({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">{label}</label>
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
