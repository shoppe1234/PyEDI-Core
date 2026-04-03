const BASE = '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

// Standards discovery types
export interface StandardVersion {
  version: string
  transaction_count: number
}

export interface StandardType {
  standard: string
  versions: StandardVersion[]
}

export interface StandardTransaction {
  code: string
  name: string
  file: string
  has_mapping: boolean
}

export interface StandardSegmentRef {
  name: string
  ref_type: string
  min_occurs: number
  max_occurs: number
  children: StandardSegmentRef[]
}

export interface StandardElementDef {
  position: number
  name: string
  data_type: string
  min_occurs: number
  max_occurs: number
}

export interface StandardSegmentDef {
  code: string
  name: string
  elements: StandardElementDef[]
}

export interface StandardSchemaResponse {
  code: string
  name: string
  version: string
  standard: string
  functional_group: string
  areas: StandardSegmentRef[][]
  segment_defs: Record<string, StandardSegmentDef>
  has_mapping: boolean
  match_key_default: Record<string, string>
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  validate: (dslPath: string, samplePath?: string) =>
    request<any>('/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dsl_path: dslPath, sample_path: samplePath }),
    }),

  validateUpload: (dslFile: File, sampleFile?: File) => {
    const form = new FormData();
    form.append('dsl_file', dslFile);
    if (sampleFile) form.append('sample_file', sampleFile);
    return request<any>('/validate/upload', { method: 'POST', body: form });
  },

  pipelineRun: (file: string) =>
    request<any[]>('/pipeline/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file }),
    }),

  pipelineResults: (status?: string, limit = 50) => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    params.set('limit', String(limit));
    return request<any[]>(`/pipeline/results?${params}`);
  },

  testCases: () => request<any[]>('/test/cases'),
  testRun: () =>
    request<any>('/test/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    }),
  testVerify: () => request<any>('/test/verify'),

  manifestEntries: (limit = 50) => request<any[]>(`/manifest?limit=${limit}`),
  manifestStats: () => request<any>('/manifest/stats'),

  config: () => request<any>('/config'),
  configRegistry: () => request<any>('/config/registry'),

  // Compare
  compareProfiles: () => request<any[]>('/compare/profiles'),
  compareRun: (profile: string, sourceDir: string, targetDir: string, matchJsonPath?: string) =>
    request<any>('/compare/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile, source_dir: sourceDir, target_dir: targetDir, match_json_path: matchJsonPath }),
    }),
  compareRuns: (profile?: string, limit = 20) => {
    const params = new URLSearchParams();
    if (profile) params.set('profile', profile);
    params.set('limit', String(limit));
    return request<any[]>(`/compare/runs?${params}`);
  },
  compareRunDetail: (runId: number) => request<any>(`/compare/runs/${runId}`),
  comparePairs: (runId: number, status?: string) => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    return request<any[]>(`/compare/runs/${runId}/pairs?${params}`);
  },
  compareDiffs: (runId: number, pairId: number) =>
    request<any[]>(`/compare/runs/${runId}/pairs/${pairId}/diffs`),
  compareExportUrl: (runId: number) => `${BASE}/compare/runs/${runId}/export`,
  compareRules: (profileName: string) => request<any>(`/compare/profiles/${profileName}/rules`),
  compareUpdateRules: (profileName: string, rules: any) =>
    request<any>(`/compare/profiles/${profileName}/rules`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rules),
    }),

  // Reclassify: re-evaluate diffs with current rules
  compareReclassify: (runId: number) =>
    request<any>(`/compare/runs/${runId}/reclassify`, { method: 'POST' }),

  // Run diff: compare two runs for new/resolved/changed errors
  compareRunDiff: (runIdA: number, runIdB: number) =>
    request<any>(`/compare/runs/${runIdA}/diff/${runIdB}`),

  // Summary: severity/segment/field breakdowns + top errors
  compareRunSummary: (runId: number) =>
    request<any>(`/compare/runs/${runId}/summary`),

  // Profile management
  profileDelete: (name: string) =>
    request<{ status: string; profile: string }>(`/onboard/profile/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),

  // Onboard wizard
  onboardRegister: (data: {
    profile_name: string;
    trading_partner: string;
    transaction_type: string;
    description: string;
    source_dsl: string;
    compiled_output: string;
    inbound_dir: string;
    match_key: Record<string, string>;
    segment_qualifiers: Record<string, string | null>;
    split_config?: Record<string, string> | null;
  }) =>
    request<{
      profile_name: string;
      rules_file: string;
      config_updated: boolean;
      rules_created: boolean;
    }>('/onboard/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  onboardSplitSuggestion: (compiledYaml: string) =>
    request<{
      split_key: string | null;
      boundary_record: string | null;
      source: string | null;
    }>(`/onboard/split-suggestion?compiled_yaml=${encodeURIComponent(compiledYaml)}`),

  onboardRulesTemplate: (compiledYaml: string) =>
    request<{
      classification: Array<{
        segment: string;
        field: string;
        severity: string;
        ignore_case: boolean;
        numeric: boolean;
      }>;
      ignore: any[];
    }>(`/onboard/rules-template?compiled_yaml=${encodeURIComponent(compiledYaml)}`),

  // X12 onboard
  onboardX12Types: () =>
    request<{
      types: Array<{
        code: string; label: string; map_file: string;
        version: string; available_versions: string[];
        category: string; description: string; has_mapping: boolean;
      }>;
    }>('/onboard/x12-types'),

  onboardX12Versions: (code: string) =>
    request<{ versions: string[] }>(`/onboard/x12-types/${encodeURIComponent(code)}/versions`),

  onboardX12Schema: (type: string, version?: string) => {
    const params = new URLSearchParams({ type });
    if (version) params.set('version', version);
    return request<{
      transaction_type: string;
      input_format: string;
      segments: string[];
      fields: Array<{ name: string; source: string; section: string }>;
      match_key_default: Record<string, string>;
    }>(`/onboard/x12-schema?${params}`);
  },

  onboardX12Validate: (type: string, samplePath: string) =>
    request<{
      transaction_type: string;
      segment_count: number;
      segments: Array<{ segment: string; fields: Array<{ name: string; content: string }> }>;
    }>('/onboard/x12-validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, sample_path: samplePath }),
    }),

  onboardX12UploadMap: (mapFile: File) => {
    const form = new FormData();
    form.append('map_file', mapFile);
    return request<{
      code: string;
      map_file: string;
      x12_schema: {
        transaction_type: string;
        input_format: string;
        segments: string[];
        fields: Array<{ name: string; source: string; section: string }>;
        match_key_default: Record<string, string>;
      };
    }>('/onboard/x12-upload-map', { method: 'POST', body: form });
  },

  // Standards discovery
  standardsCatalog: () =>
    request<{ standards: StandardType[] }>('/onboard/standards'),

  standardsTransactions: (standard: string, version: string) =>
    request<{ standard: string; version: string; transactions: StandardTransaction[] }>(
      `/onboard/standards/${encodeURIComponent(standard)}/${encodeURIComponent(version)}/transactions`
    ),

  standardsSchema: (standard: string, version: string, code: string) =>
    request<StandardSchemaResponse>(
      `/onboard/standards/${encodeURIComponent(standard)}/${encodeURIComponent(version)}/${encodeURIComponent(code)}/schema`
    ),

  // Rules tier API
  ruleTiers: () =>
    request<{
      tiers: Array<{
        tier: string;
        name: string;
        file: string;
        rule_count: number;
        ignore_count: number;
      }>;
    }>('/rules/tiers'),

  ruleUniversal: () =>
    request<{
      classification: Array<Record<string, any>>;
      ignore: Array<Record<string, any>>;
    }>('/rules/universal'),

  ruleUpdateUniversal: (rules: { classification: any[]; ignore: any[] }) =>
    request<any>('/rules/universal', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rules),
    }),

  ruleTransaction: (txnType: string) =>
    request<{
      classification: Array<Record<string, any>>;
      ignore: Array<Record<string, any>>;
    }>(`/rules/transaction/${encodeURIComponent(txnType)}`),

  ruleUpdateTransaction: (txnType: string, rules: { classification: any[]; ignore: any[] }) =>
    request<any>(`/rules/transaction/${encodeURIComponent(txnType)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rules),
    }),

  ruleDeleteTransaction: (txnType: string) =>
    request<any>(`/rules/transaction/${encodeURIComponent(txnType)}`, {
      method: 'DELETE',
    }),

  ruleEffective: (profileName: string) =>
    request<{
      rules: Array<{
        segment: string;
        field: string;
        severity: string;
        ignore_case: boolean;
        numeric: boolean;
        conditional_qualifier: string | null;
        amount_variance: number | null;
        tier: string;
      }>;
      ignore: Array<Record<string, any>>;
    }>(`/rules/effective/${encodeURIComponent(profileName)}`),

  // Field options for dropdowns
  ruleFieldOptions: (params: { profile?: string; format?: string; transaction_type?: string }) => {
    const qs = new URLSearchParams();
    if (params.profile) qs.set('profile', params.profile);
    if (params.format) qs.set('format', params.format);
    if (params.transaction_type) qs.set('transaction_type', params.transaction_type);
    return request<{
      format: string;
      segments: Array<{ name: string; label: string; fields: string[] }>;
    }>(`/rules/field-options?${qs}`);
  },

  // Discoveries: list unclassified field combos
  compareDiscoveries: (profile: string, applied?: boolean) => {
    const params = new URLSearchParams({ profile });
    if (applied !== undefined) params.set('applied', String(applied));
    return request<any[]>(`/compare/discoveries?${params}`);
  },

  // Apply discovery: promote to classification
  compareApplyDiscovery: (discoveryId: number) =>
    request<any>(`/compare/discoveries/${discoveryId}/apply`, { method: 'POST' }),
};
