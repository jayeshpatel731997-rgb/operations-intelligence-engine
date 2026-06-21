import React from 'react';
import { getWebSocketUrl } from '../services/api.js';

const initialStreamData = {
  timestamp: null,
  oee: null,
  financial_loss: null,
  top_loss: null,
  anomaly: null,
  decision: null,
  alert: '',
  event: null,
  event_history: [],
  alerts: [],
  machine_health: [],
};

export function useLiveOperations() {
  const [streamData, setStreamData] = React.useState(initialStreamData);
  const [oeeHistory, setOeeHistory] = React.useState([]);
  const [status, setStatus] = React.useState('connecting');

  React.useEffect(() => {
    let socket;
    let isMounted = true;

    try {
      socket = new WebSocket(getWebSocketUrl());
    } catch {
      setStatus('fallback');
      return undefined;
    }

    socket.onopen = () => isMounted && setStatus('live');
    socket.onerror = () => isMounted && setStatus('fallback');
    socket.onclose = () => isMounted && setStatus((current) => (current === 'live' ? 'reconnecting' : current));
    socket.onmessage = (event) => {
      if (!isMounted) return;
      const message = safeParseJson(event.data);
      if (!message || message.error) return;

      const oee = safeNumber(message.oee);
      const financialLoss = safeNumber(message.financial_loss);
      setStreamData((current) => ({
        ...current,
        ...message,
        oee: oee ?? current.oee ?? 0,
        financial_loss: financialLoss ?? current.financial_loss ?? 0,
      }));
      if (oee !== null) {
        setOeeHistory((current) => [
          ...current,
          {
            timestamp: message.timestamp,
            label: formatTime(message.timestamp),
            oee,
          },
        ].slice(-20));
      }
    };

    return () => {
      isMounted = false;
      socket?.close();
    };
  }, []);

  return { streamData, oeeHistory, status };
}

function safeParseJson(rawValue) {
  try {
    return JSON.parse(rawValue);
  } catch {
    return null;
  }
}

function safeNumber(value) {
  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : null;
}

function formatTime(timestamp) {
  if (!timestamp) return 'Waiting';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return 'Invalid';
  return date.toLocaleTimeString();
}
