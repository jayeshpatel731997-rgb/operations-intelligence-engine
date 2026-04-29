import React from 'react';
import { Activity, AlertOctagon, DollarSign, Gauge, RadioTower } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';
import AlertBanner from '../components/AlertBanner.jsx';
import DecisionPanel from '../components/DecisionPanel.jsx';
import KPICard from '../components/KPICard.jsx';
import LossChart from '../components/LossChart.jsx';
import OEEChart from '../components/OEEChart.jsx';

const API_URL = import.meta.env.VITE_API_URL || "https://operations-intelligence-engine.onrender.com";

console.log("API URL:", import.meta.env.VITE_API_URL);

const WS_PATH = '/ws';
const WS_URL = normalizeWebSocketUrl(import.meta.env.VITE_WS_URL, API_URL);
const SUMMARY_REFRESH_MS = 7000;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY_MS = 1500;

const buildQueryString = ({ machineId, startDate, endDate } = {}) => {
  const query = new URLSearchParams();
  if (machineId) query.append('machine_id', machineId);
  if (startDate) query.append('start_date', startDate);
  if (endDate) query.append('end_date', endDate);
  const qs = query.toString();
  return qs ? `?${qs}` : '';
};

const getSummary = async ({ machineId, startDate, endDate } = {}) => {
  const res = await fetch(`${API_URL}/ai-summary${buildQueryString({ machineId, startDate, endDate })}`);
  if (!res.ok) throw new Error('Failed to load summary');
  return await res.json();
};

const getDecision = async ({ machineId, startDate, endDate } = {}) => {
  const res = await fetch(`${API_URL}/ai-decision${buildQueryString({ machineId, startDate, endDate })}`);
  if (!res.ok) throw new Error('Failed to load decision');
  return await res.json();
};

const getLosses = async ({ machineId, startDate, endDate } = {}) => {
  const res = await fetch(`${API_URL}/loss${buildQueryString({ machineId, startDate, endDate })}`);
  if (!res.ok) throw new Error('Failed to load losses');
  return await res.json();
};

const uploadCsv = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_URL}/upload-data`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(payload?.detail || payload?.message || 'Failed to upload CSV');
  }

  return await res.json();
};

const downloadReport = async ({ machineId, startDate, endDate, format = 'csv' } = {}) => {
  const baseQs = buildQueryString({ machineId, startDate, endDate });
  const url = `${API_URL}/export-report${baseQs}${baseQs ? '&' : '?'}format=${encodeURIComponent(format)}`;
  const response = await fetch(url);

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => null);
    throw new Error(errorPayload?.detail || 'Unable to download report');
  }

  const blob = await response.blob();
  const filename = format === 'csv' ? 'operations-report.csv' : 'operations-report.json';
  const downloadUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = downloadUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(downloadUrl);
};

const initialStreamData = {
  timestamp: null,
  oee: null,
  financial_loss: null,
  top_loss: null,
  anomaly: null,
  decision: null,
  alert: '',
};

const fallbackLosses = [
  { loss_category: 'breakdown loss', impact: 0 },
  { loss_category: 'performance loss', impact: 0 },
  { loss_category: 'quality loss', impact: 0 },
];

function createWebSocketUrl(apiBase) {
  try {
    const url = new URL(apiBase);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = WS_PATH;
    url.search = '';
    url.hash = '';
    return url.toString();
  } catch {
    // Fallback to API_URL derived WebSocket URL
    const fallbackUrl = new URL(API_URL);
    fallbackUrl.protocol = fallbackUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    fallbackUrl.pathname = WS_PATH;
    return fallbackUrl.toString();
  }
}

function normalizeWebSocketUrl(configuredUrl, apiBase) {
  if (!configuredUrl) {
    return createWebSocketUrl(apiBase);
  }

  try {
    const url = new URL(configuredUrl);
    url.pathname = WS_PATH;
    url.search = '';
    url.hash = '';
    return url.toString();
  } catch {
    return createWebSocketUrl(apiBase);
  }
}

function formatCurrency(num) {
  const value = Number(num);
  return `$${Number.isFinite(value) ? value.toLocaleString() : '0'}`;
}

const getTrendColor = (trend) => {
  if (trend === "increase") return "text-green-500";
  if (trend === "decrease") return "text-red-500";
  return "text-yellow-500";
};

function getSeverityClass(alert, status) {
  if (alert) return 'bg-red-600 text-white';
  if (status === 'fallback') return 'bg-orange-500 text-slate-900';
  return 'bg-emerald-500 text-slate-900';
}

function formatDateTime(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return 'Invalid time';
  return date.toLocaleString();
}

function formatDelta(value) {
  if (value === null || value === undefined) return '0.00';
  return `${Number(value).toFixed(2)}`;
}

function formatTime(timestamp) {
  if (!timestamp) return 'Not connected';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return 'Invalid timestamp';
  return date.toLocaleTimeString();
}

function makeChartPoint(message) {
  return {
    timestamp: message.timestamp,
    label: formatTime(message.timestamp),
    oee: Number(message.oee ?? 0),
  };
}

function safeParseJson(rawValue) {
  try {
    return JSON.parse(rawValue);
  } catch {
    return null;
  }
}

function getTopLossName(topLossDriver) {
  if (!Array.isArray(topLossDriver) || topLossDriver.length === 0) {
    return 'no major loss driver';
  }

  const [topLoss] = topLossDriver;
  if (topLoss && typeof topLoss === 'object') {
    return String(topLoss.loss_category ?? 'unknown loss');
  }

  return String(topLoss ?? 'unknown loss');
}

function normalizeDecisionFallback(report) {
  if (!report || typeof report !== 'object') {
    return null;
  }

  const currentOee = Number(report.trend?.current_oee ?? report.oee ?? 0);
  const revenueLoss = Number(report.financial_impact?.revenue_loss ?? report.financial_loss ?? 0);
  const anomaly = String(report.anomaly ?? 'No active anomaly alerts.');
  const hasAnomaly = anomaly !== 'No active anomaly alerts.';

  return {
    timestamp: new Date().toISOString(),
    oee: Number.isFinite(currentOee) ? currentOee : 0,
    financial_loss: Number.isFinite(revenueLoss) ? revenueLoss : 0,
    top_loss: getTopLossName(report.top_loss_driver),
    anomaly,
    decision: report.decision ?? report.summary_text ?? null,
    alert: currentOee < 60 || hasAnomaly ? 'HIGH PRIORITY ISSUE DETECTED' : '',
  };
}

function useControlTowerStream({ machineId, startDate, endDate }) {
  const [streamData, setStreamData] = React.useState(initialStreamData);
  const [oeeHistory, setOeeHistory] = React.useState([]);
  const [losses, setLosses] = React.useState(fallbackLosses);
  const [status, setStatus] = React.useState('connecting');
  const [summaryData, setSummaryData] = React.useState(null);
  const [decisionData, setDecisionData] = React.useState(null);

  const loadLosses = React.useCallback(async () => {
    try {
      const nextLosses = await getLosses({ machineId, startDate, endDate });
      setLosses(Array.isArray(nextLosses) ? nextLosses : fallbackLosses);
    } catch {
      setLosses((current) => (Array.isArray(current) && current.length ? current : fallbackLosses));
    }
  }, [machineId, startDate, endDate]);

  const loadSummary = React.useCallback(async () => {
    try {
      const summary = await getSummary({ machineId, startDate, endDate });
      setSummaryData((current) => (summary && typeof summary === 'object' && !Array.isArray(summary) ? summary : current));
    } catch (error) {
      console.error('Failed to load summary:', error);
    }
  }, [machineId, startDate, endDate]);

  const loadDecision = React.useCallback(async () => {
    try {
      const decision = await getDecision({ machineId, startDate, endDate });
      setDecisionData((current) => (decision && typeof decision === 'object' && !Array.isArray(decision) ? decision : current));
    } catch (error) {
      console.error('Failed to load decision:', error);
    }
  }, [machineId, startDate, endDate]);

  const applyStreamMessage = React.useCallback((message) => {
    if (!message || typeof message !== 'object' || message.error) return;

    const financialLoss = Number(message.financial_loss ?? 0);
    const oee = Number(message.oee ?? 0);
    setStreamData((current) => ({
      ...current,
      ...message,
      financial_loss: Number.isFinite(financialLoss) ? financialLoss : current.financial_loss ?? 0,
      oee: Number.isFinite(oee) ? oee : current.oee ?? 0,
    }));
    setOeeHistory((current) => [...current, makeChartPoint(message)].slice(-20));
    loadLosses();
  }, [loadLosses]);

  const loadDecisionFallback = React.useCallback(async () => {
    try {
      const report = await getDecision({ machineId, startDate, endDate });
      const fallbackMessage = normalizeDecisionFallback(report);
      if (fallbackMessage) {
        applyStreamMessage(fallbackMessage);
      }
    } catch {
      setStreamData((current) => ({
        ...current,
        anomaly: current.anomaly || 'No stream data yet',
        decision: current.decision || 'Decision service is temporarily unavailable.',
      }));
    }
  }, [applyStreamMessage, machineId, startDate, endDate]);

  React.useEffect(() => {
    let isMounted = true;
    let socket = null;
    let reconnectTimer = null;
    let reconnectAttempts = 0;

    loadLosses();
    loadSummary();
    loadDecision();

    const scheduleReconnect = () => {
      if (!isMounted) return;

      if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        setStatus('offline');
        return;
      }

      reconnectAttempts += 1;
      setStatus('reconnecting');
      reconnectTimer = window.setTimeout(connect, RECONNECT_DELAY_MS * reconnectAttempts);
    };

    const connect = () => {
      try {
        socket = new WebSocket(WS_URL);
      } catch {
        setStatus('fallback');
        loadDecisionFallback();
        scheduleReconnect();
        return;
      }

      socket.onopen = () => {
        if (!isMounted) return;
        reconnectAttempts = 0;
        setStatus('live');
      };

      socket.onmessage = (event) => {
        if (!isMounted) return;
        applyStreamMessage(safeParseJson(event.data));
      };

      socket.onerror = () => {
        if (!isMounted) return;
        setStatus('fallback');
        loadDecisionFallback();

        // fallback if websocket fails
        setTimeout(async () => {
          try {
            const summary = await getSummary({ machineId, startDate, endDate });
            const decision = await getDecision({ machineId, startDate, endDate });

            setSummaryData((current) => (summary && typeof summary === 'object' && !Array.isArray(summary) ? summary : current));
            setDecisionData((current) => (decision && typeof decision === 'object' && !Array.isArray(decision) ? decision : current));
          } catch (error) {
            console.error('Fallback failed', error);
          }
        }, 2000);

        socket?.close();
      };

      socket.onclose = () => {
        if (!isMounted) return;
        scheduleReconnect();
      };
    };

    connect();

    return () => {
      isMounted = false;
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
      }
      socket?.close();
    };
  }, [applyStreamMessage, loadDecisionFallback, loadLosses, loadSummary, loadDecision]);

  // Initial load useEffect
  React.useEffect(() => {
    loadSummary();
    loadDecision();
  }, [loadSummary, loadDecision]);

  React.useEffect(() => {
    loadSummary();
    loadDecision();

    const interval = window.setInterval(() => {
      loadSummary();
      loadDecision();
    }, SUMMARY_REFRESH_MS);

    return () => window.clearInterval(interval);
  }, [loadSummary, loadDecision]);

  const refreshData = React.useCallback(() => {
    loadLosses();
    loadSummary();
    loadDecision();
  }, [loadLosses, loadSummary, loadDecision]);

  return { streamData, oeeHistory, losses, status, summaryData, decisionData, refreshData };
}

export default function Dashboard() {
  const [selectedMachine, setSelectedMachine] = React.useState('');
  const [timeFilter, setTimeFilter] = React.useState('24h');
  const [customStart, setCustomStart] = React.useState('');
  const [customEnd, setCustomEnd] = React.useState('');
  const [uploadStatus, setUploadStatus] = React.useState('');
  const [uploadError, setUploadError] = React.useState('');
  const [useCsvSource, setUseCsvSource] = React.useState(false);

  const today = new Date();
  const formatDate = (date) => date.toISOString().split('T')[0];
  const startDate =
    timeFilter === '7d'
      ? formatDate(new Date(Date.now() - 7 * 24 * 60 * 60 * 1000))
      : timeFilter === '24h'
      ? formatDate(new Date(Date.now() - 24 * 60 * 60 * 1000))
      : customStart || null;
  const endDate = timeFilter === 'custom' ? customEnd || null : formatDate(today);

  const { streamData, oeeHistory, losses, status, summaryData, decisionData, refreshData } = useControlTowerStream({
    machineId: selectedMachine || undefined,
    startDate,
    endDate,
  });

  const dataSource = useCsvSource ? 'Uploaded CSV' : 'Live Stream';
  const activeMachines = selectedMachine ? 1 : 3;
  const lastUpdated = summaryData?.last_updated
    ? formatDateTime(summaryData.last_updated)
    : streamData.timestamp
    ? formatDateTime(streamData.timestamp)
    : 'Waiting for live data';
  const summaryDelta = summaryData?.delta ?? 0;
  const revenue = summaryData?.financial?.revenue_loss ?? 0;

  const handleUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploadStatus('Uploading CSV...');
    setUploadError('');

    try {
      await uploadCsv(file);
      setUseCsvSource(true);
      setUploadStatus('CSV uploaded successfully. Analysis refreshed.');
      refreshData();
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Upload failed');
      setUploadStatus('');
    } finally {
      event.target.value = '';
    }
  };

  const hasLiveData = streamData.timestamp !== null;
  const alertStatus = streamData.alert ? 'High priority' : status === 'live' ? 'Normal' : 'Connecting';
  const oeeValue = streamData.oee === null ? 'Waiting...' : `${Number(streamData.oee || 0).toFixed(1)}%`;
  const revenueLoss = streamData.financial_loss === null ? 'Waiting...' : formatCurrency(streamData.financial_loss);
  const topLoss = streamData.top_loss || 'Waiting...';
  const anomalyText = streamData.anomaly || 'No anomaly data yet';

  return (
    <div className="p-6 bg-slate-900 min-h-screen text-white">
      {/* HEADER */}
      <h1 className="text-3xl font-bold mb-6">
        Operations Intelligence Dashboard
      </h1>
      <p className="text-gray-400 mb-6">
        Real-time OEE tracking, anomaly detection, and industrial decision support
      </p>

      {/* SYSTEM STATUS BAR */}
      <div className="mb-4 rounded-xl border border-slate-700 bg-slate-800 p-4 text-sm text-slate-200 shadow-sm">
        <div className="grid gap-3 md:grid-cols-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Data Source</p>
            <p className="text-base font-semibold">{dataSource}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Last Updated</p>
            <p className="text-base font-semibold">{lastUpdated}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Active Machines</p>
            <p className="text-base font-semibold">{activeMachines}</p>
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-3">
            <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${getSeverityClass(streamData.alert, status)}`}>
              {streamData.alert ? 'Critical' : status === 'fallback' ? 'Warning' : 'Stable'}
            </span>
            <span className="text-slate-400">{streamData.alert ? 'Urgent attention required' : status === 'fallback' ? 'Degraded mode' : 'All systems normal'}</span>
          </div>
        </div>
      </div>

      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          <label className="cursor-pointer inline-flex items-center rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-100 transition hover:border-slate-500">
            <span>Upload CSV</span>
            <input
              type="file"
              accept=".csv"
              onChange={handleUpload}
              className="sr-only"
            />
          </label>

          <div className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-100">
            <label htmlFor="machine-filter" className="text-slate-300">Machine:</label>
            <select
              id="machine-filter"
              value={selectedMachine}
              onChange={(event) => setSelectedMachine(event.target.value)}
              className="rounded-md border border-slate-600 bg-slate-900 px-2 py-1 text-sm text-white outline-none focus:border-slate-400"
            >
              <option value="">All</option>
              <option value="M1">M1</option>
              <option value="M2">M2</option>
              <option value="M3">M3</option>
            </select>
          </div>

          <div className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-100">
            <button
              type="button"
              onClick={() => setTimeFilter('24h')}
              className={`rounded px-3 py-1 transition ${timeFilter === '24h' ? 'bg-slate-700 text-white' : 'bg-slate-900 text-slate-300 hover:bg-slate-700'}`}
            >
              Last 24h
            </button>
            <button
              type="button"
              onClick={() => setTimeFilter('7d')}
              className={`rounded px-3 py-1 transition ${timeFilter === '7d' ? 'bg-slate-700 text-white' : 'bg-slate-900 text-slate-300 hover:bg-slate-700'}`}
            >
              Last 7 days
            </button>
          </div>

          <button
            type="button"
            onClick={() =>
              downloadReport({ machineId: selectedMachine || undefined, startDate, endDate, format: 'csv' }).catch((error) => {
                console.error(error);
                setUploadError(error instanceof Error ? error.message : 'Report download failed');
              })
            }
            className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-100 transition hover:border-slate-500"
          >
            Download Report
          </button>

          {uploadStatus && <span className="text-sm text-green-300">{uploadStatus}</span>}
          {uploadError && <span className="text-sm text-red-300">{uploadError}</span>}
        </div>
      </div>

      {/* CRITICAL ISSUE ALERT */}
      {summaryData?.top_losses?.[0] && (
        <div className="bg-red-600 p-4 rounded-xl mb-6">
          🚨 Critical Issue: {summaryData.top_losses[0].loss_category}
        </div>
      )}

      {/* KPI GRID */}
      {summaryData && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <div className="bg-slate-800 p-5 rounded-xl shadow-lg">
            <p className="text-gray-400">OEE</p>
            <div className="flex items-center gap-3">
              <h2 className="text-3xl font-bold text-green-400">{summaryData.average_oee}%</h2>
              <span className={`text-sm font-semibold ${summaryDelta >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>
                {summaryDelta >= 0 ? '↑' : '↓'} {formatDelta(summaryDelta)} pts
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-400">vs previous period</p>
          </div>

          <div className="bg-slate-800 p-5 rounded-xl shadow-lg">
            <p className="text-gray-400">Revenue Loss</p>
              <h2 className="text-3xl font-bold text-red-400">
              {formatCurrency(revenue)}
            </h2>
            <p className="mt-2 text-xs text-slate-400">Trend: {summaryData.trend_direction}</p>
          </div>

          <div className="bg-slate-800 p-5 rounded-xl shadow-lg">
            <p className="text-gray-400">Trend</p>
            <h2 className={`text-3xl font-bold ${getTrendColor(summaryData.trend_direction)}`}>
              {summaryData.trend_direction}
            </h2>
            <p className="mt-2 text-xs text-slate-400">{summaryData.current_oee?.toFixed(2)}% current OEE</p>
          </div>
        </div>
      )}

      {/* CHART + AI */}
      {summaryData && (
        <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-6 mb-6">
          {/* chart */}
          <div className="bg-slate-800 p-5 rounded-xl shadow-lg">
            <h3 className="text-xl font-bold mb-4">Loss Analysis</h3>
            <BarChart width={400} height={250} data={summaryData.top_losses}>
              <XAxis dataKey="loss_category" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="impact" />
            </BarChart>
          </div>

          {/* AI summary split */}
          <div className="space-y-4">
            <div className="bg-slate-800 p-5 rounded-xl shadow-lg">
              <h3 className="text-xl font-bold mb-3">Insight</h3>
              <p className="text-slate-300">{summaryData.summary_report}</p>
            </div>

            <div className="bg-slate-800 p-5 rounded-xl shadow-lg">
              <h3 className="text-xl font-bold mb-3">Root Cause</h3>
              <p className="text-slate-300">
                {summaryData.top_losses?.[0]
                  ? `Primary driver is ${summaryData.top_losses[0].loss_category}.`
                  : 'No clear root cause identified yet.'}
              </p>
            </div>

            <div className="bg-slate-800 p-5 rounded-xl shadow-lg">
              <h3 className="text-xl font-bold mb-3">Recommended Action</h3>
              <div className="flex flex-wrap items-center gap-3 mb-3">
                <span className={`rounded-full px-3 py-1 text-sm font-semibold uppercase ${
                  decisionData?.priority === 'HIGH'
                    ? 'bg-red-600 text-white'
                    : decisionData?.priority === 'MEDIUM'
                    ? 'bg-amber-400 text-slate-900'
                    : 'bg-emerald-500 text-slate-900'
                }`}>
                  {decisionData?.priority || 'LOW'}
                </span>
                <span className="text-slate-400 text-sm">Severity indicator</span>
              </div>
              <p className="text-slate-300">{decisionData?.action || 'Review the top loss driver and apply corrective actions.'}</p>
            </div>
          </div>
        </div>
      )}

      {/* TECH STACK FOOTER */}
      <div className="mt-10 rounded-xl border border-slate-700 bg-slate-900 p-4 text-xs text-slate-400">
        Powered by FastAPI + React | Simulated Industrial Data | Designed for real-time decision support
      </div>
    </div>
  );
}
