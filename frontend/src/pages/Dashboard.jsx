import React from 'react';
import { Activity, AlertOctagon, DollarSign, Gauge, RadioTower } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';
import AlertBanner from '../components/AlertBanner.jsx';
import DecisionPanel from '../components/DecisionPanel.jsx';
import KPICard from '../components/KPICard.jsx';
import LossChart from '../components/LossChart.jsx';
import OEEChart from '../components/OEEChart.jsx';

const BASE_URL = "https://operations-intelligence-engine.onrender.com";

const getSummary = async () => {
  const res = await fetch(`${BASE_URL}/ai-summary`);
  return await res.json();
};

const getLosses = async () => {
  const res = await fetch(`${BASE_URL}/loss`);
  return await res.json();
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

function formatCurrency(num) {
  return `$${Number(num).toLocaleString()}`;
}

const getTrendColor = (trend) => {
  if (trend === "increase") return "text-green-500";
  if (trend === "decrease") return "text-red-500";
  return "text-yellow-500";
};

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
  const [summaryData, setSummaryData] = React.useState(null);
  const [decisionData, setDecisionData] = React.useState(null);

  const loadLosses = React.useCallback(async () => {
    try {
      const nextLosses = await getLosses();
      setLosses(Array.isArray(nextLosses) ? nextLosses : fallbackLosses);
    } catch {
      setLosses((current) => (Array.isArray(current) && current.length ? current : fallbackLosses));
    }
  }, []);

  const loadSummary = React.useCallback(async () => {
    try {
      const summary = await getSummary();
      setSummaryData(summary);
    } catch (error) {
      console.error('Failed to load summary:', error);
    }
  }, []);

  const loadDecision = React.useCallback(async () => {
    try {
      const decision = await getDecision();
      setDecisionData(decision);
    } catch (error) {
      console.error('Failed to load decision:', error);
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
      const report = await getDecision();
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
            const summary = await getSummary();
            const decision = await getDecision();

            setSummaryData(summary);
            setDecisionData(decision);

            console.log("Fallback API loaded");
          } catch (err) {
            console.error("Fallback failed", err);
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
  }, []);

  return { streamData, oeeHistory, losses, status, summaryData, decisionData };
}

export default function Dashboard() {
  const { streamData, oeeHistory, losses, status, summaryData, decisionData } = useControlTowerStream();
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
        Real-time OEE tracking, anomaly detection, and AI-driven decision support system
      </p>

      {/* SYSTEM STATUS */}
      <div className="mb-4 flex items-center gap-2">
        <div className="w-3 h-3 bg-green-500 rounded-full"></div>
        <span className="text-sm text-gray-400">
          System Live — Real-time Analytics Active
        </span>
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
            <h2 className="text-3xl font-bold text-green-400">
              {summaryData.average_oee}%
            </h2>
          </div>

          <div className="bg-slate-800 p-5 rounded-xl shadow-lg">
            <p className="text-gray-400">Revenue Loss</p>
            <h2 className="text-3xl font-bold text-red-400">
              {formatCurrency(summaryData.revenue_loss)}
            </h2>
          </div>

          <div className="bg-slate-800 p-5 rounded-xl shadow-lg">
            <p className="text-gray-400">Trend</p>
            <h2 className={`text-3xl font-bold ${getTrendColor(summaryData.trend_direction)}`}>
              {summaryData.trend_direction}
            </h2>
          </div>
        </div>
      )}

      {/* CHART + AI */}
      {summaryData && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
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

          {/* AI summary */}
          <div className="bg-slate-800 p-5 rounded-xl shadow-lg">
            <h3 className="text-xl font-bold mb-4">AI Insights</h3>
            <div className="text-gray-300">
              {summaryData.summary_report}
            </div>
          </div>
        </div>
      )}

      {/* DECISION PANEL */}
      {decisionData && (
        <div className="bg-gradient-to-r from-purple-500 to-indigo-600 p-6 rounded-xl text-white shadow-xl">
          <h2 className="text-xl font-bold mb-2">AI Recommendation</h2>
          <p>{decisionData.summary_text}</p>
        </div>
      )}

      {/* TECH STACK FOOTER */}
      <p className="text-xs text-gray-500 mt-10">
        Built using FastAPI, React, Machine Learning & deployed on cloud infrastructure
      </p>
    </div>
  );
}
