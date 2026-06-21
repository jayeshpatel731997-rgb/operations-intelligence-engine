import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import React from 'react';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('recharts', () => ({
  Bar: () => null,
  BarChart: ({ children }) => children,
  CartesianGrid: () => null,
  Line: () => null,
  LineChart: ({ children }) => children,
  ResponsiveContainer: ({ children }) => children,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

import { App } from './main.jsx';

let backendContract;

class MockWebSocket {
  static instances = [];
  static message = null;

  constructor() {
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      this.onopen?.();
      this.onmessage?.({ data: JSON.stringify(MockWebSocket.message) });
    }, 0);
  }

  close() {}
}

describe('Control tower dashboard', () => {
  beforeAll(() => {
    backendContract = loadFastApiDashboardContract();
    expectLiveDashboardContractShape(backendContract);
  });

  beforeEach(() => {
    MockWebSocket.instances = [];
    MockWebSocket.message = backendContract.stream;
    global.WebSocket = MockWebSocket;
    global.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
    global.fetch = vi.fn((url) => {
      const requestUrl = String(url);
      if (requestUrl.includes('/ai-summary')) {
        return Promise.resolve({ ok: true, json: async () => backendContract.summary });
      }
      if (requestUrl.includes('/ai-decision')) {
        return Promise.resolve({ ok: true, json: async () => backendContract.decision });
      }
      if (requestUrl.includes('/predictive-maintenance')) {
        return Promise.resolve({ ok: true, json: async () => backendContract.predictive });
      }
      if (requestUrl.includes('/events/recent')) {
        return Promise.resolve({ ok: true, json: async () => backendContract.events });
      }
      return Promise.resolve({ ok: true, json: async () => backendContract.losses });
    });
  });

  it('renders live summary data, last updated, financials, and decision guidance', async () => {
    render(<App />);

    expect(screen.getByText('Waiting for live data')).toBeInTheDocument();
    expect(await screen.findByText('Operations Intelligence Dashboard')).toBeInTheDocument();
    expect(screen.getByText('AI-powered Operations Control Tower')).toBeInTheDocument();
    await expectTextRendered(`${backendContract.summary.average_oee.toFixed(1)}%`);
    await expectTextRendered(formatExpectedCurrency(backendContract.summary.financial.revenue_loss));
    expect(screen.getByText('PlantOS Control Tower')).toBeInTheDocument();
    expect(screen.getByText('Breakdown spike')).toBeInTheDocument();
    expect(screen.getByText('Machine Health Matrix')).toBeInTheDocument();
    expect(screen.getByText('Decision Center')).toBeInTheDocument();
    expect(screen.getByText('Predictive Risk Panel')).toBeInTheDocument();
    expect(screen.getByText('Simulation Studio')).toBeInTheDocument();
    expect(screen.getByText('Live Operations Feed')).toBeInTheDocument();
    expect(screen.getByText('Critical Issues')).toBeInTheDocument();
    await expectTextRendered(backendContract.summary.critical_alerts[0].action);
    expect(screen.getAllByText(backendContract.summary.top_losses[0].loss_category).length).toBeGreaterThan(0);
    await expectTextRendered(backendContract.decision.recommended_action);
    expect(screen.queryByText('$NaN')).not.toBeInTheDocument();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/ai-summary'));
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('scenario=normal'));
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/ai-decision'));
    });
  });

  it('renders dashboard data from the live FastAPI websocket and API contract', async () => {
    render(<App />);

    expect(await screen.findByText('Operations Intelligence Dashboard')).toBeInTheDocument();
    await expectTextRendered(`${backendContract.summary.average_oee.toFixed(1)}%`);
    await expectTextRendered(formatExpectedCurrency(backendContract.summary.financial.revenue_loss));
    await expectTextRendered(backendContract.decision.recommended_action);
    expect(screen.getAllByText(backendContract.summary.top_losses[0].loss_category).length).toBeGreaterThan(0);
    await expectTextRendered(backendContract.stream.event_history[0].title);
    await expectTextRendered(backendContract.predictive[0].recommended_action);
  });
});

async function expectTextRendered(text) {
  expect((await screen.findAllByText(text)).length).toBeGreaterThan(0);
}

function loadFastApiDashboardContract() {
  const testFilePath = fileURLToPath(import.meta.url);
  const frontendDir = path.resolve(path.dirname(testFilePath), '..');
  const repoRoot = path.resolve(frontendDir, '..');
  const python = process.env.PYTHON || 'python';
  const script = `
import contextlib
import io
import json
import sys
from pathlib import Path

repo = Path.cwd()
sys.path.insert(0, str(repo / "backend"))

with contextlib.redirect_stdout(io.StringIO()):
    import main
    from fastapi.testclient import TestClient

    with TestClient(main.app) as client:
        summary = client.get("/ai-summary?scenario=normal").json()
        decision = client.get("/ai-decision").json()
        losses = client.get("/loss").json()
        predictive = client.get("/predictive-maintenance").json()
        events = client.get("/events/recent").json()
        with client.websocket_connect("/ws") as websocket:
            stream = websocket.receive_json()

print(json.dumps({
    "summary": summary,
    "decision": decision,
    "stream": stream,
    "losses": losses,
    "predictive": predictive,
    "events": events,
}))
`;

  return JSON.parse(execFileSync(python, ['-c', script], {
    cwd: repoRoot,
    encoding: 'utf8',
    env: { ...process.env, PYTHONPATH: path.join(repoRoot, 'backend') },
    maxBuffer: 10 * 1024 * 1024,
  }));
}

function expectLiveDashboardContractShape(contract) {
  expect(contract.summary).toEqual(expect.objectContaining({
    average_oee: expect.any(Number),
    financial: expect.objectContaining({ revenue_loss: expect.any(Number) }),
    top_losses: expect.arrayContaining([
      expect.objectContaining({ loss_category: expect.any(String), impact: expect.any(Number) }),
    ]),
  }));
  expect(contract.decision).toEqual(expect.objectContaining({
    recommended_action: expect.any(String),
    financial_impact: expect.objectContaining({ revenue_loss: expect.any(Number) }),
  }));
  expect(contract.stream).toEqual(expect.objectContaining({
    timestamp: expect.any(String),
    oee: expect.any(Number),
    financial_loss: expect.any(Number),
    event_history: expect.arrayContaining([
      expect.objectContaining({ title: expect.any(String), timestamp: expect.any(String) }),
    ]),
    machine_health: expect.any(Array),
    alerts: expect.any(Array),
  }));
  expect(contract.predictive).toEqual(expect.arrayContaining([
    expect.objectContaining({ machine: expect.any(String), recommended_action: expect.any(String) }),
  ]));
}

function formatExpectedCurrency(value) {
  return `$${Number(value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}
