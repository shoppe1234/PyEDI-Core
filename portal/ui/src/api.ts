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
