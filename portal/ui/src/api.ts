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
};
