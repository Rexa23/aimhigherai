'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Zap, Megaphone, CheckCircle, Users } from 'lucide-react';

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
}

const agents: Agent[] = [
  {
    id: 'hunter',
    name: 'Hunter',
    description: 'Discovers high-potential projects across chains',
    icon: <Zap className="h-5 w-5" />,
  },
  {
    id: 'outreach',
    name: 'Outreach',
    description: 'Initiates authentic conversations at scale',
    icon: <Megaphone className="h-5 w-5" />,
  },
  {
    id: 'qualification',
    name: 'Qualification',
    description: 'Validates fit and scores opportunities',
    icon: <CheckCircle className="h-5 w-5" />,
  },
  {
    id: 'onboarding',
    name: 'Onboarding',
    description: 'Schedules partnerships and handoffs',
    icon: <Users className="h-5 w-5" />,
  },
];

export const AgentNetwork: React.FC = () => {
  return (
    <section id="agents" className="landing-shell relative overflow-hidden py-24">
      <div className="mx-auto w-full max-w-6xl px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          viewport={{ once: true, margin: '-100px' }}
          className="mb-16"
        >
          <h2 className="landing-title text-5xl font-bold mb-3">Coordinated Agent Network</h2>
          <p className="landing-subtitle">Four specialized agents work together with deterministic rules. No bottlenecks, no human delays.</p>
        </motion.div>

        {/* Agents Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {agents.map((agent, index) => (
            <motion.div
              key={agent.id}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: index * 0.08 }}
              viewport={{ once: true, margin: '-100px' }}
              className="landing-card p-6"
            >
              <div className="flex items-start gap-4">
                <div className="h-12 w-12 rounded-lg bg-green-500/10 flex items-center justify-center text-green-500 flex-shrink-0">
                  {agent.icon}
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white mb-1">{agent.name} Agent</h3>
                  <p className="text-sm text-zinc-400">{agent.description}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          viewport={{ once: true, margin: '-100px' }}
          className="mt-16 border-t border-white/8 pt-12"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { label: 'Routing Latency', value: '420ms' },
              { label: 'Signal Confidence', value: '94.2%' },
              { label: 'Cross-Agent Sync', value: '99.99%' },
              { label: 'Message Queue', value: '< 100ms' },
            ].map((stat) => (
              <div key={stat.label}>
                <p className="text-xs uppercase tracking-widest text-zinc-600 mb-2">{stat.label}</p>
                <p className="text-xl font-semibold text-white">{stat.value}</p>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
};
