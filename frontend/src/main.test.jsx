import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
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

class MockWebSocket {
  static instances = [];

  constructor() {
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      this.onopen?.();
      this.onmessage?.({ data: JSON.stringify(streamMessage) });
    }, 0);
  }

  close() {
    this.onclose?.();
  }
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
    global.fetch = vi.fn(() => Promise.resolve({
      ok: true,
      json: async () => lossResponse,
    }));
  });

  it('renders real-time stream data, charts, alert banner, and decision panel', async () => {
    render(<App />);

    expect(screen.getByText('Waiting for live data...')).toBeInTheDocument();
    expect(await screen.findByText('Real-Time OEE Decision Dashboard')).toBeInTheDocument();
    expect(await screen.findByText('84.3%')).toBeInTheDocument();
    expect(screen.getByText('$1,003,921')).toBeInTheDocument();
    expect(screen.getByText('breakdown loss')).toBeInTheDocument();
    expect(screen.getByText('HIGH PRIORITY ISSUE DETECTED')).toBeInTheDocument();
    expect(screen.getByText('OEE over time')).toBeInTheDocument();
    expect(screen.getByText('Loss breakdown')).toBeInTheDocument();
    expect(screen.getByText('Recommend maintenance intervention on the highest-loss machine.')).toBeInTheDocument();
  });
});
