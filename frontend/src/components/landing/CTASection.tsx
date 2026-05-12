'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';

export const CTASection: React.FC = () => {
  return (
    <section className="landing-shell relative overflow-hidden py-28">
      <div className="mx-auto w-full max-w-4xl text-center px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          viewport={{ once: true, margin: '-100px' }}
        >
          <h2 className="landing-title text-6xl font-bold mb-6 leading-tight">
            Scale Web3 partnerships with AI agents
          </h2>
          <p className="landing-subtitle mx-auto max-w-2xl mb-12">
            Replace manual prospecting with autonomous discovery, qualification, and onboarding. Built for teams who demand measurable results.
          </p>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
            viewport={{ once: true }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16"
          >
            <button className="landing-btn-primary inline-flex items-center gap-2 rounded-md px-6 py-3 text-sm font-semibold">
              Start Building
              <ArrowRight className="h-4 w-4" />
            </button>
            <a
              href="#platform"
              className="inline-flex items-center gap-2 rounded-md border border-white/20 px-6 py-3 text-sm font-semibold text-zinc-300 hover:text-white hover:border-white/40 transition-colors"
            >
              Learn More
            </a>
          </motion.div>

          {/* Trust indicators */}
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            viewport={{ once: true }}
            className="border-t border-white/8 pt-12 grid grid-cols-3 gap-8"
          >
            {[
              { label: '99.99% Uptime', desc: 'Enterprise SLA' },
              { label: 'Enterprise Security', desc: 'Fully Audited' },
              { label: '24/7 Support', desc: 'Dedicated Team' },
            ].map((item) => (
              <div key={item.label}>
                <p className="text-xs uppercase tracking-widest text-zinc-600 mb-1">{item.label}</p>
                <p className="text-sm font-medium text-zinc-400">{item.desc}</p>
              </div>
            ))}
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
};
