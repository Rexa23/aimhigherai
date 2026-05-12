'use client';

import React from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';

const statItems = [
  { label: 'Projects Discovered', value: '3,284' },
  { label: 'Success Rate', value: '92%' },
  { label: 'Time to Partnership', value: '8.2d' },
];

export const Hero: React.FC = () => {
  return (
    <section id="platform" className="landing-shell relative overflow-hidden pt-32 md:pt-40">
      <div className="relative z-10 mx-auto w-full max-w-6xl px-8 pb-24">
        {/* Main Content */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
          className="max-w-3xl"
        >
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.05 }}
            className="landing-eyebrow mb-8"
          >
            AI Onboarding Platform
          </motion.p>

          <h1 className="landing-title text-[56px] md:text-[72px] font-bold mb-6 leading-tight">
            Scale Web3 partnerships with autonomous agents
          </h1>

          <p className="landing-subtitle mb-8 max-w-2xl">
            Discover teams, qualify fit, and execute onboarding at scale. AimHigher reduces manual prospecting work from weeks to days.
          </p>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
            className="flex items-center gap-4 mb-16"
          >
            <button className="landing-btn-primary rounded-md px-6 py-2.5 text-sm font-semibold inline-flex items-center gap-2">
              Get Started
              <ArrowRight className="h-4 w-4" />
            </button>
            <a
              href="#agents"
              className="text-sm font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Learn how it works →
            </a>
          </motion.div>
        </motion.div>

        {/* Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
          className="grid grid-cols-3 gap-12 border-t border-white/8 pt-12"
        >
          {statItems.map((stat, index) => (
            <div key={stat.label}>
              <p className="text-xs uppercase tracking-widest text-zinc-600 mb-2">{stat.label}</p>
              <p className="text-2xl font-semibold text-white">{stat.value}</p>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
};
