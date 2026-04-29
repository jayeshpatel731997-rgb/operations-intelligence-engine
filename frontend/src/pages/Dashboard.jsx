import React from 'react';
import { Activity, AlertOctagon, DollarSign, Gauge, RadioTower } from 'lucide-react';
import AlertBanner from '../components/AlertBanner.jsx';
import DecisionPanel from '../components/DecisionPanel.jsx';
import KPICard from '../components/KPICard.jsx';
import LossChart from '../components/LossChart.jsx';
import OEEChart from '../components/OEEChart.jsx';

const API_BASE = (import.meta.env.VITE_API_BASE ?? 'http://localhost:8000').replace(/\/$/, '');
const WS_PATH = '/ws';
const WS_URL = normalizeWebSocketUrl(import.meta.env.VITE_WS_URL, API_BASE);
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY_MS = 1500;

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
    return `ws://localhost:8000${WS_PATH}`;
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

function formatCurrency(value) {
  return Number(value || 0).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  });
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

async function fetchJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`${path} request failed`);
  }

  return response.json();
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
  const anomaly = String(report.anomaly ?? 'No active anomaly alerts.');
  const hasAnomaly = anomaly !== 'No active anomaly alerts.';

  return {
    timestamp: new Date().toISOString(),
    oee: currentOee,
    financial_loss: Number(report.financial_impact?.revenue_loss ?? report.financial_loss ?? 0),
    top_loss: getTopLossName(report.top_loss_driver),
    anomaly,
    decision: report.decision ?? report.summary_text ?? null,
    alert: currentOee < 60 || hasAnomaly ? 'HIGH PRIORITY ISSUE DETECTED' : '',
  };
}

function useControlTowerStream() {
  const [streamData, setStreamData] = React.useState(initialStreamData);
  const [oeeHistory, setOeeHistory] = React.useState([]);
  const [losses, setLosses] = React.useState(fallbackLosses);
  const [status, setStatus] = React.useState('connecting');

  const loadLosses = React.useCallback(async () => {
    try {
      const nextLosses = await fetchJson('/loss');
      setLosses(Array.isArray(nextLosses) ? nextLosses : fallbackLosses);
    } catch {
      setLosses((current) => (Array.isArray(current) && current.length ? current : fallbackLosses));
    }
  }, []);

  const applyStreamMessage = React.useCallback((message) => {
    if (!message || typeof message !== 'object' || message.error) return;

    setStreamData((current) => ({ ...current, ...message }));
    setOeeHistory((current) => [...current, makeChartPoint(message)].slice(-20));
    loadLosses();
  }, [loadLosses]);

  const loadDecisionFallback = React.useCallback(async () => {
    try {
      const report = await fetchJson('/ai-decision');
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
  }, [applyStreamMessage]);

  React.useEffect(() => {
    let isMounted = true;
    let socket = null;
    let reconnectTimer = null;
    let reconnectAttempts = 0;

    loadLosses();

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
  }, [applyStreamMessage, loadDecisionFallback, loadLosses]);

  return { streamData, oeeHistory, losses, status };
}

export default function Dashboard() {
  const { streamData, oeeHistory, losses, status } = useControlTowerStream();
  const hasLiveData = streamData.timestamp !== null;
  const alertStatus = streamData.alert ? 'High priority' : status === 'live' ? 'Normal' : 'Connecting';
  const oeeValue = streamData.oee === null ? 'Waiting...' : `${Number(streamData.oee || 0).toFixed(1)}%`;
  const revenueLoss = streamData.financial_loss === null ? 'Waiting...' : formatCurrency(streamData.financial_loss);
  const topLoss = streamData.top_loss || 'Waiting...';
  const anomalyText = streamData.anomaly || 'No anomaly data yet';

  return (
    <main className="min-h-screen bg-slate-950 px-5 py-6 text-slate-100 sm:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6 rounded-3xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl shadow-slate-950/20">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h1 className="text-3xl font-bold text-white">
                Operations Intelligence Control Tower
              </h1>
              <p className="text-gray-400">
                Real-Time OEE | Anomaly Detection | AI Decision Engine
              </p>
            </div>

            <div className="text-green-400 font-semibold">
              🟢 LIVE SYSTEM
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between gap-4 lg:flex-col lg:items-end">
            <div className="rounded-lg border border-slate-700 bg-slate-950/80 px-4 py-3 text-sm text-slate-300">
              <span className="font-semibold text-slate-100">Stream:</span> {status} |{' '}
              <span className="font-semibold text-slate-100">Last update:</span> {formatTime(streamData.timestamp)}
            </div>
          </div>
        </header>

        {!hasLiveData && (
          <section className="mb-5 rounded-lg border border-cyan-400/25 bg-cyan-400/10 p-4 text-cyan-100">
            Waiting for live data...
          </section>
        )}

        <AlertBanner alert={streamData.alert} anomaly={streamData.anomaly} />

        <section className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <KPICard title="OEE" value={oeeValue} detail="Current streamed OEE" icon={Gauge} tone="cyan" />
          <KPICard title="Revenue Loss" value={revenueLoss} detail="Estimated current loss" icon={DollarSign} tone="amber" />
          <KPICard title="Top Loss" value={topLoss} detail="Largest current loss driver" icon={Activity} tone="emerald" />
          <KPICard title="Alert Status" value={alertStatus} detail={anomalyText} icon={AlertOctagon} tone={streamData.alert ? 'red' : 'cyan'} />
        </section>

        <section className="grid gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <OEEChart points={oeeHistory} />
          </div>
          <LossChart losses={losses} />
        </section>

        <section className="mt-5">
          <DecisionPanel decision={streamData.decision} anomaly={streamData.anomaly} />
        </section>

        <footer className="mt-10 text-center text-gray-500">
          Built by Jayesh Patel | Supply Chain Analytics
        </footer>
      </div>
    </main>
  );
}
