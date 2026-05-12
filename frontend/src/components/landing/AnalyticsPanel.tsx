'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, CartesianGrid, Tooltip } from 'recharts';
import { TrendingUp, Users, Zap, Rocket } from 'lucide-react';

const conversionData = [
  { m: 'Jan', rate: 17 },
  { m: 'Feb', rate: 21 },
  { m: 'Mar', rate: 24 },
  { m: 'Apr', rate: 29 },
  { m: 'May', rate: 33 },
  { m: 'Jun', rate: 36 },
];

const discoveryData = [
  { m: 'Jan', leads: 220 },
  { m: 'Feb', leads: 264 },
  { m: 'Mar', leads: 301 },
  { m: 'Apr', leads: 348 },
  { m: 'May', leads: 392 },
  { m: 'Jun', leads: 447 },
];

const onboardingData = [
  { m: 'Jan', active: 8 },
  { m: 'Feb', active: 12 },
  { m: 'Mar', active: 18 },
  { m: 'Apr', active: 31 },
  { m: 'May', active: 44 },
  { m: 'Jun', active: 58 },
];

export const AnalyticsPanel: React.FC = () => {
  return (
    <section id="analytics" className="landing-shell relative overflow-hidden py-24">
      <div className="mx-auto w-full max-w-6xl px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          viewport={{ once: true, margin: '-100px' }}
          className="mb-16"
        >
          <h2 className="landing-title text-5xl font-bold mb-3">Real-time Intelligence</h2>
          <p className="landing-subtitle">Operational metrics for growth teams. Every chart tuned for decision-making.</p>
        </motion.div>

        {/* Key Metrics */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ duration: 0.4, staggerChildren: 0.05 }}
          viewport={{ once: true, margin: '-100px' }}
          className="mb-12 grid grid-cols-2 md:grid-cols-4 gap-4"
        >
          {[
            { label: 'Conversion Rate', value: '36%', icon: TrendingUp },
            { label: 'Leads Discovered', value: '1,972', icon: Users },
            { label: 'Active Onboarding', value: '58', icon: Rocket },
            { label: 'Campaigns', value: '42', icon: Zap },
          ].map(({ label, value, icon: Icon }) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              viewport={{ once: true }}
              className="landing-card p-4"
            >
              <div className="flex items-start justify-between mb-3">
                <p className="text-xs uppercase tracking-widest text-zinc-600">{label}</p>
                <Icon className="h-4 w-4 text-green-500" />
              </div>
              <p className="text-3xl font-bold text-white">{value}</p>
            </motion.div>
          ))}
        </motion.div>

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {[
            { title: 'Conversion Trend', data: conversionData, key: 'rate', suffix: '%' },
            { title: 'Lead Discovery', data: discoveryData, key: 'leads', suffix: '' },
            { title: 'Onboarding Growth', data: onboardingData, key: 'active', suffix: '' },
          ].map((chart, idx) => (
            <motion.div
              key={chart.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: idx * 0.06 }}
              viewport={{ once: true, margin: '-100px' }}
              className="landing-card p-6"
            >
              <h3 className="text-sm font-semibold text-white mb-1">{chart.title}</h3>
              <p className="text-xs text-zinc-600 mb-6">Last 6 months</p>
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={chart.data}>
                  <defs>
                    <linearGradient id={`gradient-${idx}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.1} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(255, 255, 255, 0.05)" vertical={false} />
                  <XAxis dataKey="m" stroke="rgba(255, 255, 255, 0.2)" tick={{ fontSize: 12 }} />
                  <YAxis stroke="rgba(255, 255, 255, 0.2)" tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      background: 'rgba(10, 10, 15, 0.9)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      borderRadius: '6px',
                    }}
                    labelStyle={{ color: '#f5f5f7', fontSize: '11px' }}
                  />
                  <Area type="monotone" dataKey={chart.key} stroke="#22c55e" strokeWidth={2} fill={`url(#gradient-${idx})`} />
                </AreaChart>
              </ResponsiveContainer>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};
