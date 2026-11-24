import type { CompareResponse, Options, Status, ValuateResponse, ValuationJob, VehicleProfile } from './types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  status: () => request<Status>('/api/status'),
  decode: (vin: string) => request<VehicleProfile>(`/api/decode/${encodeURIComponent(vin)}`),
  valuate: (vin: string, options: Options, zip?: string) =>
    request<ValuateResponse>('/api/valuate', {
      method: 'POST',
      body: JSON.stringify({ vin, options, zip: zip || null }),
    }),
  /**
   * Start a valuation job and poll it until it finishes. A cold vehicle is 150-250 eBay
   * calls, which can outlast a proxy timeout as one request; the job form never does.
   */
  valuateJob: async (
    vin: string,
    options: Options,
    zip: string | undefined,
    onProgress?: (done: number, total: number) => void,
  ): Promise<ValuateResponse> => {
    let job = await request<ValuationJob>('/api/valuate/start', {
      method: 'POST',
      body: JSON.stringify({ vin, options, zip: zip || null }),
    });
    onProgress?.(job.done, job.total);
    while (job.status === 'running') {
      await new Promise((r) => setTimeout(r, 1000));
      job = await request<ValuationJob>(`/api/valuate/jobs/${job.job_id}`);
      onProgress?.(job.done, job.total);
    }
    if (job.status === 'error' || !job.result) throw new Error(job.error || 'Valuation failed');
    return job.result;
  },
  compare: (valuation: ValuateResponse, instant_offer: number, private_party: number, hourly_value: number) =>
    request<CompareResponse>('/api/compare', {
      method: 'POST',
      body: JSON.stringify({ valuation, instant_offer, private_party, hourly_value }),
    }),
};

export const money = (n: number, digits = 0) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: digits });
