const API_URL = import.meta.env.VITE_API_URL || 'https://operations-intelligence-engine.onrender.com';
const WS_PATH = '/ws';

export const SCENARIOS = [
  { id: 'normal', label: 'Normal' },
  { id: 'breakdown_spike', label: 'Breakdown spike' },
  { id: 'quality_issue', label: 'Quality issue' },
];

export const SIMULATION_ACTIONS = [
  'reduce downtime',
  'improve speed',
  'reduce defects',
  'add maintenance',
  'add shift',
];

export function buildQueryString({ machineId, plantId, lineId, startDate, endDate, scenario } = {}) {
  const query = new URLSearchParams();
  if (plantId) query.append('plant_id', plantId);
  if (lineId) query.append('line_id', lineId);
  if (machineId) query.append('machine_id', machineId);
  if (startDate) query.append('start_date', startDate);
  if (endDate) query.append('end_date', endDate);
  if (scenario) query.append('scenario', scenario);
  const qs = query.toString();
  return qs ? `?${qs}` : '';
}

export function getWebSocketUrl() {
  const configuredUrl = import.meta.env.VITE_WS_URL;
  try {
    const url = new URL(configuredUrl || API_URL);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = WS_PATH;
    url.search = '';
    url.hash = '';
    return url.toString();
  } catch {
    return 'ws://localhost:8000/ws';
  }
}

export async function getSummary(filters = {}) {
  return getJson(`/ai-summary${buildQueryString(filters)}`, 'Failed to load summary');
}

export async function getDecision(filters = {}) {
  return getJson(`/ai-decision${buildQueryString(filters)}`, 'Failed to load decision');
}

export async function getLosses(filters = {}) {
  return getJson(`/loss${buildQueryString(filters)}`, 'Failed to load losses');
}

export async function getPredictiveMaintenance(filters = {}) {
  return getJson(`/predictive-maintenance${buildQueryString(filters)}`, 'Failed to load predictive maintenance');
}

export async function getRecentEvents() {
  return getJson('/events/recent', 'Failed to load recent events');
}

export async function runSimulation(payload) {
  const response = await fetch(`${API_URL}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => null);
    throw new Error(errorPayload?.detail || 'Simulation failed');
  }
  return response.json();
}

export async function uploadCsv(file) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${API_URL}/upload-data`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || payload?.message || 'Failed to upload CSV');
  }
  return response.json();
}

export async function downloadReport(filters = {}, format = 'pdf') {
  const baseQs = buildQueryString(filters);
  const url = `${API_URL}/export-report${baseQs}${baseQs ? '&' : '?'}format=${encodeURIComponent(format)}`;
  const response = await fetch(url);
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => null);
    throw new Error(errorPayload?.detail || 'Unable to download report');
  }
  const blob = await response.blob();
  const extension = format === 'csv' ? 'csv' : 'pdf';
  const filename = `operations-executive-report.${extension}`;
  const downloadUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = downloadUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(downloadUrl);
}

async function getJson(path, message) {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) throw new Error(message);
  return response.json();
}
