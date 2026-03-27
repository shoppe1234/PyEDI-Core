const BASE = '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
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
