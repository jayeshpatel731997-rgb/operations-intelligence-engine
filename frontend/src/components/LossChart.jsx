import React from 'react';
import { BarChart } from 'recharts/es6/chart/BarChart';
import { Bar } from 'recharts/es6/cartesian/Bar';
import { CartesianGrid } from 'recharts/es6/cartesian/CartesianGrid';
import { XAxis } from 'recharts/es6/cartesian/XAxis';
import { YAxis } from 'recharts/es6/cartesian/YAxis';
import { ResponsiveContainer } from 'recharts/es6/component/ResponsiveContainer';
import { Tooltip } from 'recharts/es6/component/Tooltip';

function formatCurrency(value) {
  return Number(value || 0).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  });
}

export default function LossChart({ losses }) {
  const safeLosses = Array.isArray(losses) ? losses : [];

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900/80 p-5 shadow-2xl shadow-black/20">
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-white">Loss breakdown</h2>
        <p className="text-sm text-slate-400">Financial impact by loss driver</p>
      </div>
      <div className="h-72 min-h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={safeLosses} layout="vertical" margin={{ left: 18 }}>
            <CartesianGrid stroke="#1f2a44" strokeDasharray="4 4" />
            <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 12 }} tickFormatter={(value) => `$${Math.round(value / 1000)}k`} />
            <YAxis dataKey="loss_category" type="category" width={130} tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <Tooltip
              contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, color: '#e2e8f0' }}
              formatter={(value) => formatCurrency(value)}
            />
            <Bar dataKey="impact" fill="#f59e0b" radius={[0, 6, 6, 0]} isAnimationActive />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
