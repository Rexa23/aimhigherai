'use client';

import React from 'react';
import { motion } from 'framer-motion';

interface ProjectCard {
  id: string;
  name: string;
  score: number;
}

const stages = [
  {
    key: 'discovery',
    label: 'Discovery',
    projects: [
      { id: '1', name: 'Axiom Liquidity', score: 78 },
      { id: '2', name: 'Nexa Rollup', score: 71 },
    ],
  },
  {
    key: 'qualified',
    label: 'Qualified',
    projects: [
      { id: '3', name: 'Vector Bridge', score: 92 },
      { id: '4', name: 'Nova Staking', score: 88 },
    ],
  },
  {
    key: 'onboarding',
    label: 'Onboarding',
    projects: [{ id: '5', name: 'Orbit Protocol', score: 94 }],
  },
  {
    key: 'active',
    label: 'Active',
    projects: [{ id: '6', name: 'Nexus Sync', score: 96 }],
  },
];

export const PipelineBoard: React.FC = () => {
  return (
    <section id="pipeline" className="landing-shell relative overflow-hidden py-24">
      <div className="mx-auto w-full max-w-6xl px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          viewport={{ once: true, margin: '-100px' }}
          className="mb-16"
        >
          <h2 className="landing-title text-5xl font-bold mb-3">Pipeline Operations</h2>
          <p className="landing-subtitle">Real-time project progression through your growth funnel</p>
        </motion.div>

        {/* Kanban */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ duration: 0.4, staggerChildren: 0.06 }}
          viewport={{ once: true, margin: '-100px' }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
        >
          {stages.map((stage, stageIndex) => (
            <motion.div
              key={stage.key}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: stageIndex * 0.08 }}
              viewport={{ once: true, margin: '-100px' }}
            >
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-white mb-1">{stage.label}</h3>
                <p className="text-xs text-zinc-600">{stage.projects.length} projects</p>
              </div>

              <div className="space-y-3">
                {stage.projects.map((project) => (
                  <motion.div
                    key={project.id}
                    whileHover={{ y: -2 }}
                    transition={{ duration: 0.15 }}
                    className="landing-card p-3"
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <p className="text-sm font-medium text-white line-clamp-2 flex-1">{project.name}</p>
                      <div className="text-xs font-semibold text-zinc-400">{project.score}</div>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-green-500 to-emerald-500 rounded-full"
                        initial={{ width: 0 }}
                        whileInView={{ width: `${project.score}%` }}
                        transition={{ duration: 0.6, ease: 'easeOut', delay: 0.2 }}
                        viewport={{ once: true }}
                      />
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
};
