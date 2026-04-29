import React from 'react';

export default function KPICard({ title, value, detail, icon: Icon, tone = 'cyan' }) {
  const toneClasses = {
    cyan: 'border-cyan-400/25 bg-cyan-400/10 text-cyan-200',
    emerald: 'border-emerald-400/25 bg-emerald-400/10 text-emerald-200',
    amber: 'border-amber-400/25 bg-amber-400/10 text-amber-200',
    red: 'border-red-400/30 bg-red-500/10 text-red-200',
  };

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900/80 p-5 shadow-2xl shadow-black/20 transition duration-300 hover:border-slate-500">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-400">{title}</p>
          <strong className="mt-2 block truncate text-3xl font-bold text-white">{value}</strong>
          <span className="mt-2 block text-sm text-slate-400">{detail}</span>
        </div>
        {Icon ? (
          <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg border ${toneClasses[tone] ?? toneClasses.cyan}`}>
            <Icon size={22} />
          </div>
        ) : null}
      </div>
    </section>
  );
}
