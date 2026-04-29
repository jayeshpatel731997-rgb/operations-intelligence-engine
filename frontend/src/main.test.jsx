import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './main.jsx';

const streamMessage = {
  timestamp: '2026-04-25T18:41:36.761017+00:00',
  oee: 84.32,
  top_loss: 'breakdown loss',
  anomaly: 'downtime spike detected on M3.',
  financial_loss: 1003921,
  decision: 'Recommend maintenance intervention on the highest-loss machine.',
  alert: 'HIGH PRIORITY ISSUE DETECTED',
};

const lossResponse = [
  { loss_category: 'breakdown loss', duration: 45, impact: 18000 },
  { loss_category: 'performance loss', duration: 30, impact: 9000 },
];

const summaryResponse = {
  last_updated: '2026-04-25T18:41:37.761017+00:00',
  average_oee: 84.2,
  current_oee: 85.1,
  previous_oee: 84.1,
  delta: 1,
  trend_direction: 'increase',
  top_losses: lossResponse,
  financial: {
    revenue_loss: 123456.78,
    formatted: '$123,457',
  },
  anomalies: [],
  summary_report: 'OEE is improving with breakdown loss as the main driver.',
};

const decisionResponse = {
  priority: 'HIGH',
  action: 'Recommend maintenance intervention on the highest-loss machine.',
};

class MockWebSocket {
  static instances = [];

  constructor() {
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      this.onopen?.();
      this.onmessage?.({ data: JSON.stringify(streamMessage) });
    }, 0);
  }

  close() {}
}

describe('Control tower dashboard', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    global.WebSocket = MockWebSocket;
    global.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
    global.fetch = vi.fn((url) => {
      const requestUrl = String(url);
      if (requestUrl.includes('/ai-summary')) {
        return Promise.resolve({ ok: true, json: async () => summaryResponse });
      }
      if (requestUrl.includes('/ai-decision')) {
        return Promise.resolve({ ok: true, json: async () => decisionResponse });
      }
      return Promise.resolve({ ok: true, json: async () => lossResponse });
    });
  });

  it('renders live summary data, last updated, financials, and decision guidance', async () => {
    render(<App />);

    expect(screen.getByText('Waiting for live data')).toBeInTheDocument();
    expect(await screen.findByText('Operations Intelligence Dashboard')).toBeInTheDocument();
    expect(await screen.findByText('84.2%')).toBeInTheDocument();
    expect(screen.getByText('$123,456.78')).toBeInTheDocument();
    expect(screen.getAllByText('breakdown loss').length).toBeGreaterThan(0);
    expect(screen.getByText('Recommend maintenance intervention on the highest-loss machine.')).toBeInTheDocument();
    expect(screen.queryByText('$NaN')).not.toBeInTheDocument();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/ai-summary'));
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/ai-decision'));
    });
  });
});
