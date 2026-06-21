import React from 'react';
import { Activity, AlertOctagon, BarChart3, BrainCircuit, Factory, FileDown, Gauge, ShieldAlert, Sparkles, Upload, Wrench } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { SCENARIOS, SIMULATION_ACTIONS } from '../services/api.js';

export function Header({ scenarioLabel }) {
  return (
    <header className="mb-6 flex flex-col gap-4 border-b border-slate-800 pb-5 md:flex-row md:items-end md:justify-between">
      <div>
        <div className="mb-2 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-800 text-cyan-200">
            <Factory size={20} aria-hidden="true" />
          </span>
          <p className="text-sm font-semibold uppercase tracking-wide text-cyan-200">PlantOS Control Tower</p>
        </div>
        <h1 className="text-3xl font-bold">Operations Intelligence Dashboard</h1>
        <p className="mt-2 text-gray-400">AI-powered Operations Control Tower</p>
      </div>
      <div className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-sm text-slate-300">
        Scenario: <span className="font-semibold text-white">{scenarioLabel}</span>
      </div>
    </header>
  );
}

export function ScopeControls({
  plantId,
  lineId,
  machineId,
  scenario,
  scopeOptions,
  onPlantChange,
  onLineChange,
  onMachineChange,
  onScenarioChange,
  onUpload,
  onDownload,
  uploadStatus,
  uploadError,
}) {
  const plants = scopeOptions?.plants?.length ? scopeOptions.plants : [{ id: 'PLANT_A', label: 'Austin Cell A' }, { id: 'PLANT_B', label: 'Detroit Cell B' }];
  const lines = scopeOptions?.lines?.length ? scopeOptions.lines : [{ id: 'LINE_1', label: 'Line 1' }, { id: 'LINE_2', label: 'Line 2' }];
  const machines = scopeOptions?.machines?.length ? scopeOptions.machines : [{ id: 'M1', label: 'M1' }, { id: 'M2', label: 'M2' }, { id: 'M3', label: 'M3' }];

  return (
    <section className="mb-4 flex flex-col gap-3 rounded-lg border border-slate-800 bg-slate-900 py-2 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-wrap items-center gap-2">
        <label className="inline-flex cursor-pointer items-center rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-100 transition hover:border-slate-500">
          <Upload className="mr-2" size={16} aria-hidden="true" />
          <span>Upload CSV</span>
          <input type="file" accept=".csv" onChange={onUpload} className="sr-only" />
        </label>
        <Select label="Plant" value={plantId} onChange={onPlantChange} options={[{ id: '', label: 'All plants' }, ...plants]} />
        <Select label="Line" value={lineId} onChange={onLineChange} options={[{ id: '', label: 'All lines' }, ...lines]} />
        <Select label="Machine" value={machineId} onChange={onMachineChange} options={[{ id: '', label: 'All machines' }, ...machines]} />
        <button type="button" onClick={() => onDownload('pdf')} className="inline-flex items-center rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20">
          <FileDown className="mr-2" size={16} aria-hidden="true" />
          Download Executive Report
        </button>
        <button type="button" onClick={() => onDownload('csv')} className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-100 transition hover:border-slate-500">
          CSV Export
        </button>
        {uploadStatus && <span className="text-sm text-green-300">{uploadStatus}</span>}
        {uploadError && <span className="text-sm text-red-300">{uploadError}</span>}
      </div>
      <div className="flex items-center gap-2 overflow-x-auto rounded-lg border border-slate-700 bg-slate-800 p-1">
        {SCENARIOS.map((item) => (
          <button key={item.id} type="button" onClick={() => onScenarioChange(item.id)} className={`whitespace-nowrap rounded-md px-3 py-1.5 text-sm transition ${scenario === item.id ? 'bg-slate-100 text-slate-950' : 'text-slate-300 hover:bg-slate-700 hover:text-white'}`}>
            {item.label}
          </button>
        ))}
      </div>
    </section>
  );
}

export function StatusBar({ dataSource, lastUpdated, activeMachines, status, alert }) {
  return (
    <section className="mb-4 rounded-lg border border-slate-700 bg-slate-800 p-4 text-sm text-slate-200 shadow-sm">
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Data Source" value={dataSource} />
        <Metric label="Last Updated" value={lastUpdated} />
        <Metric label="Active Machines" value={activeMachines} />
        <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-3">
          <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${alert ? 'bg-red-600 text-white' : status === 'fallback' ? 'bg-orange-500 text-slate-900' : 'bg-emerald-500 text-slate-900'}`}>
            {alert ? 'Critical' : status === 'fallback' ? 'Warning' : 'Stable'}
          </span>
          <span className="text-slate-400">{alert || (status === 'fallback' ? 'Degraded mode' : 'All systems normal')}</span>
        </div>
      </div>
    </section>
  );
}

export function ExecutiveSummary({ summaryData, streamData, isLoading }) {
  if (isLoading && !summaryData) return <SkeletonGrid />;
  const revenue = summaryData?.financial?.revenue_loss ?? 0;
  const delta = summaryData?.delta ?? 0;
  const currentOee = summaryData?.current_oee ?? streamData.oee ?? 0;
  return (
    <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-4">
      <Kpi title="OEE" value={`${safeFixed(summaryData?.average_oee ?? currentOee, 1)}%`} tone="text-emerald-300" detail={`${delta >= 0 ? 'Up' : 'Down'} ${safeFixed(Math.abs(delta), 2)} pts`} />
      <Kpi title="Revenue Loss" value={formatCurrency(revenue)} tone="text-red-300" detail="Live recomputed loss" />
      <Kpi title="Trend" value={summaryData?.trend_direction || 'stable'} tone={summaryData?.trend_direction === 'decrease' ? 'text-red-300' : 'text-cyan-200'} detail={`${safeFixed(currentOee, 2)}% current OEE`} />
      <Kpi title="Risk Signals" value={`${summaryData?.predictive_risk?.length ?? 0}`} tone="text-amber-200" detail="Machines under model watch" />
    </section>
  );
}

export function DecisionCenter({ decisionData }) {
  const priority = decisionData?.priority || 'LOW';
  return (
    <section className="rounded-lg border border-slate-700 bg-slate-800 p-5 shadow-lg">
      <SectionTitle icon={BrainCircuit} title="Decision Center" subtitle="Executive action recommendation" />
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <span className={`rounded-full px-3 py-1 text-xs font-bold ${priority === 'HIGH' ? 'bg-red-600 text-white' : priority === 'MEDIUM' ? 'bg-amber-400 text-slate-950' : 'bg-emerald-500 text-slate-950'}`}>{priority}</span>
          <h3 className="mt-4 text-2xl font-bold">{decisionData?.issue || 'Operational Loss'}</h3>
          <p className="mt-2 text-sm text-slate-300">{decisionData?.recommended_action || decisionData?.action || 'Review the top loss driver and apply corrective actions.'}</p>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Metric label="Machine" value={decisionData?.machine || decisionData?.highest_loss_machine?.machine || 'M1'} />
          <Metric label="Impact" value={formatCurrency(decisionData?.financial_impact?.revenue_loss ?? 0)} />
          <Metric label="Time-to-action" value={decisionData?.time_to_action || 'within 24 hours'} />
          <Metric label="Confidence" value={`${safeFixed((decisionData?.confidence ?? 0.8) * 100, 0)}%`} />
          <Metric label="Expected improvement" value={`${safeFixed(decisionData?.expected_oee_gain ?? 0, 1)} pts`} />
          <Metric label="Estimated savings" value={formatCurrency(decisionData?.estimated_savings ?? 0)} />
        </div>
      </div>
      <button type="button" className="mt-4 rounded-lg bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300">
        Create Action Plan
      </button>
    </section>
  );
}

export function PredictiveRiskPanel({ predictiveData }) {
  const items = predictiveData?.slice(0, 4) ?? [];
  return (
    <section className="rounded-lg border border-slate-700 bg-slate-800 p-5 shadow-lg">
      <SectionTitle icon={ShieldAlert} title="Predictive Risk Panel" subtitle="Failure probability and remaining useful life" />
      <div className="mt-4 space-y-3">
        {items.length ? items.map((item) => (
          <div key={`${item.plant_id}-${item.line_id}-${item.machine}`} className="rounded-lg border border-slate-700 bg-slate-900 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold">{item.machine}</p>
                <p className="text-xs text-slate-400">{item.plant_id} / {item.line_id}</p>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${item.severity === 'HIGH' ? 'bg-red-600 text-white' : item.severity === 'MEDIUM' ? 'bg-amber-400 text-slate-950' : 'bg-emerald-500 text-slate-950'}`}>{item.severity}</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-700">
              <div className="h-full bg-cyan-300" style={{ width: `${Math.min(Number(item.failure_risk || 0) * 100, 100)}%` }} />
            </div>
            <p className="mt-3 text-sm text-slate-300">{item.recommended_action}</p>
            <p className="mt-2 text-xs text-slate-500">{item.remaining_hours} hours remaining useful life</p>
          </div>
        )) : <EmptyState text="No risk signals in the selected scope." />}
      </div>
    </section>
  );
}

export function SimulationStudio({ action, improvementPercent, setAction, setImprovementPercent, result, isRunning, error, onRun }) {
  return (
    <section className="rounded-lg border border-slate-700 bg-slate-800 p-5 shadow-lg">
      <SectionTitle icon={Sparkles} title="Simulation Studio" subtitle="Model operational improvements before committing action" />
      <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_120px_auto]">
        <select value={action} onChange={(event) => setAction(event.target.value)} className="rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300">
          {SIMULATION_ACTIONS.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <input type="number" min="1" max="60" value={improvementPercent} onChange={(event) => setImprovementPercent(event.target.value)} className="rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300" />
        <button type="button" onClick={onRun} className="rounded-lg bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300">
          {isRunning ? 'Running' : 'Simulate'}
        </button>
      </div>
      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
      {result ? (
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <Metric label="Current OEE" value={`${safeFixed(result.current_oee, 1)}%`} />
          <Metric label="Projected OEE" value={`${safeFixed(result.projected_oee, 1)}%`} />
          <Metric label="Revenue saved" value={formatCurrency(result.revenue_saved)} />
          <Metric label="Decision" value={result.decision} />
        </div>
      ) : <p className="mt-4 text-sm text-slate-400">Run a scenario to compare OEE and revenue impact.</p>}
    </section>
  );
}

export function LiveOperationsFeed({ events, streamData }) {
  const feed = streamData?.event_history?.length ? streamData.event_history : events;
  return (
    <section className="rounded-lg border border-slate-700 bg-slate-800 p-5 shadow-lg">
      <SectionTitle icon={Activity} title="Live Operations Feed" subtitle="Rotating anomaly events and alert timeline" />
      <div className="mt-4 space-y-3">
        {feed?.slice(0, 6).map((event) => (
          <div key={event.id || `${event.timestamp}-${event.title}`} className="flex gap-3 rounded-lg border border-slate-700 bg-slate-900 p-3">
            <span className={`mt-1 h-2.5 w-2.5 rounded-full ${event.severity === 'HIGH' ? 'bg-red-400' : event.severity === 'MEDIUM' ? 'bg-amber-300' : 'bg-emerald-300'}`} />
            <div>
              <p className="text-sm font-semibold">{event.title || 'Live event'} <span className="text-slate-500">/ {event.machine}</span></p>
              <p className="text-xs text-slate-400">{event.description || event.anomaly || 'Machine condition changed'} · {formatDateTime(event.timestamp)}</p>
            </div>
          </div>
        )) || <EmptyState text="Waiting for live operations events." />}
      </div>
    </section>
  );
}

export function MachineHealthMatrix({ health, machineMetrics }) {
  const rows = health?.length ? health : machineMetrics?.map((item) => ({ machine: item.machine, oee: item.oee, status: item.oee < 82 ? 'Watch' : 'Healthy', severity: item.oee < 82 ? 'MEDIUM' : 'LOW', top_loss: item.top_loss })) ?? [];
  return (
    <section className="rounded-lg border border-slate-700 bg-slate-800 p-5 shadow-lg">
      <SectionTitle icon={Gauge} title="Machine Health Matrix" subtitle="Current state across the selected operating scope" />
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {rows.length ? rows.map((item) => (
          <div key={item.machine} className="rounded-lg border border-slate-700 bg-slate-900 p-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-lg font-semibold">{item.machine}</p>
              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${item.status === 'Critical' ? 'bg-red-600 text-white' : item.status === 'Watch' ? 'bg-amber-400 text-slate-950' : 'bg-emerald-500 text-slate-950'}`}>{item.status}</span>
            </div>
            <p className="text-2xl font-bold text-emerald-300">{safeFixed(item.oee, 1)}%</p>
            <p className="mt-2 text-xs text-slate-400">Top loss: {item.top_loss || 'none'}</p>
          </div>
        )) : <EmptyState text="No machine health data available." />}
      </div>
    </section>
  );
}

export function CriticalIssues({ alerts }) {
  if (!alerts?.length) return null;
  return (
    <section className="mb-6 rounded-lg border border-slate-700 bg-slate-800 p-5 shadow-lg">
      <SectionTitle icon={AlertOctagon} title="Critical Issues" subtitle="Top 3 by financial impact" />
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        {alerts.slice(0, 3).map((alert) => (
          <div key={`${alert.issue}-${alert.financial_impact}`} className="rounded-lg border border-slate-700 bg-slate-900 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h3 className="font-semibold capitalize text-white">{alert.issue}</h3>
              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${alert.severity === 'HIGH' ? 'bg-red-600 text-white' : 'bg-amber-400 text-slate-950'}`}>{alert.severity}</span>
            </div>
            <p className="mb-4 text-sm leading-relaxed text-slate-300">{alert.action}</p>
            <Metric label="Financial impact" value={formatCurrency(alert.financial_impact)} />
          </div>
        ))}
      </div>
    </section>
  );
}

export function LossAndTrend({ summaryData, oeeHistory }) {
  return (
    <section className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
      <div className="rounded-lg border border-slate-700 bg-slate-800 p-5 shadow-lg">
        <SectionTitle icon={BarChart3} title="Loss Analysis" subtitle="Financial impact by OEE loss family" />
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={250}>
            <BarChart data={summaryData?.top_losses ?? []}>
              <CartesianGrid stroke="#1e293b" vertical={false} />
              <XAxis dataKey="loss_category" stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
              <YAxis stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }} labelStyle={{ color: '#e2e8f0' }} />
              <Bar dataKey="impact" fill="#38bdf8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="rounded-lg border border-slate-700 bg-slate-800 p-5 shadow-lg">
        <SectionTitle icon={Activity} title="OEE Trend" subtitle="Live stream samples" />
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={250}>
            <LineChart data={oeeHistory}>
              <CartesianGrid stroke="#1e293b" vertical={false} />
              <XAxis dataKey="label" stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis domain={[70, 100]} stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }} />
              <Line type="monotone" dataKey="oee" stroke="#34d399" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
}

function Select({ label, value, onChange, options }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-100">
      <label className="text-slate-300">{label}:</label>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="rounded-md border border-slate-600 bg-slate-900 px-2 py-1 text-sm text-white outline-none focus:border-slate-400">
        {options.map((item) => <option key={`${label}-${item.id}`} value={item.id}>{item.label}</option>)}
      </select>
    </div>
  );
}

function SectionTitle({ icon: Icon, title, subtitle }) {
  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-2">
        <Icon className="text-cyan-200" size={18} aria-hidden="true" />
        <h2 className="text-xl font-bold">{title}</h2>
      </div>
      <p className="text-sm text-slate-400">{subtitle}</p>
    </div>
  );
}

function Kpi({ title, value, detail, tone }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800 p-5 shadow-lg">
      <p className="text-sm text-gray-400">{title}</p>
      <h2 className={`mt-2 text-3xl font-bold ${tone}`}>{value}</h2>
      <p className="mt-2 text-xs text-slate-400">{detail}</p>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-base font-semibold text-white">{value}</p>
    </div>
  );
}

function EmptyState({ text }) {
  return <div className="rounded-lg border border-dashed border-slate-700 p-4 text-sm text-slate-400">{text}</div>;
}

function SkeletonGrid() {
  return (
    <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-4">
      {[0, 1, 2, 3].map((item) => <div key={item} className="h-32 animate-pulse rounded-lg bg-slate-800" />)}
    </section>
  );
}

export function formatCurrency(num) {
  const value = Number(num ?? 0);
  return `$${Number.isFinite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '0'}`;
}

export function formatDateTime(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return 'Waiting for live data';
  return date.toLocaleString();
}

function safeFixed(value, digits) {
  const number = Number(value ?? 0);
  return Number.isFinite(number) ? number.toFixed(digits) : (0).toFixed(digits);
}
