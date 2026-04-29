import React from 'react';
import { Brain } from 'lucide-react';

export default function DecisionPanel({ decision, anomaly }) {
  const text = decision || 'Waiting for decision recommendation from the real-time stream.';
  const anomalyText = anomaly || 'No anomaly data yet';

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900/80 p-5 shadow-2xl shadow-black/20">
      <div className="mb-4 flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-lg border border-violet-400/25 bg-violet-400/10 text-violet-200">
          <Brain size={20} />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-white">AI Decision Panel</h2>
          <p className="text-sm text-slate-400">Decision summary from backend stream</p>
        </div>
      </div>
      <p className="leading-7 text-slate-200">{text}</p>
      <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950/80 p-3 text-sm text-slate-400">
        <span className="font-semibold text-slate-300">Anomaly status:</span> {anomalyText}
      </div>
    </section>
  );
}
