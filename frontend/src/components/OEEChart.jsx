import React from 'react';
import { LineChart } from 'recharts/es6/chart/LineChart';
import { Line } from 'recharts/es6/cartesian/Line';
import { CartesianGrid } from 'recharts/es6/cartesian/CartesianGrid';
import { XAxis } from 'recharts/es6/cartesian/XAxis';
import { YAxis } from 'recharts/es6/cartesian/YAxis';
import { ResponsiveContainer } from 'recharts/es6/component/ResponsiveContainer';
import { Tooltip } from 'recharts/es6/component/Tooltip';

export default function OEEChart({ points }) {
  const safePoints = Array.isArray(points) ? points : [];

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900/80 p-5 shadow-2xl shadow-black/20">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-white">OEE over time</h2>
          <p className="text-sm text-slate-400">Last {safePoints.length} streaming updates</p>
        </div>
      </div>
      <div className="h-72 min-h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={safePoints}>
            <CartesianGrid stroke="#1f2a44" strokeDasharray="4 4" />
            <XAxis dataKey="label" tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <YAxis domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <Tooltip
              contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, color: '#e2e8f0' }}
              formatter={(value) => `${Number(value).toFixed(1)}%`}
            />
            <Line type="monotone" dataKey="oee" stroke="#22d3ee" strokeWidth={3} dot={false} isAnimationActive />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
