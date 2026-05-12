'use client';

import React from 'react';
import { motion } from 'framer-motion';

const messages = [
  {
    who: 'user',
    text: 'We\'re launching a new perpetual DEX next quarter. Looking for strategic partnerships.',
  },
  {
    who: 'ai',
    text: 'Strong community growth trajectory and excellent on-chain metrics. You qualify for partnership.',
  },
  {
    who: 'ai',
    text: 'I\'ve started onboarding with our team and can provide key ecosystem introductions.',
  },
  {
    who: 'user',
    text: 'Perfect. Let\'s schedule a call with your partnerships team.',
  },
];

export const ConversationPreview: React.FC = () => {
  return (
    <section id="conversations" className="landing-shell relative overflow-hidden py-24">
      <div className="mx-auto w-full max-w-6xl px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          viewport={{ once: true, margin: '-100px' }}
          className="mb-16"
        >
          <h2 className="landing-title text-5xl font-bold mb-3">Authentic Conversations</h2>
          <p className="landing-subtitle">
            Messages adapt to project context. Every signal is preserved for your team's onboarding workflow.
          </p>
        </motion.div>

        {/* Chat Preview */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          viewport={{ once: true, margin: '-100px' }}
          className="landing-card overflow-hidden max-w-2xl"
        >
          {/* Header */}
          <div className="border-b border-white/8 px-6 py-4">
            <h3 className="text-sm font-semibold text-white">Delta Perps</h3>
            <p className="text-xs text-zinc-600 mt-1">Active conversation</p>
          </div>

          {/* Messages */}
          <div className="px-6 py-6 space-y-6">
            {messages.map((msg, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: index * 0.06 }}
                viewport={{ once: true }}
                className={`flex ${msg.who === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-xs rounded-lg px-4 py-2.5 text-sm leading-relaxed ${
                    msg.who === 'user'
                      ? 'bg-green-500/10 text-white border border-green-500/20'
                      : 'bg-white/5 text-zinc-200 border border-white/10'
                  }`}
                >
                  {msg.text}
                </div>
              </motion.div>
            ))}
          </div>

          {/* Footer Stats */}
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.3 }}
            viewport={{ once: true }}
            className="border-t border-white/8 px-6 py-4 grid grid-cols-3 gap-4"
          >
            {[
              { label: 'Qualification Score', value: '89/100' },
              { label: 'Sentiment', value: 'High Intent' },
              { label: 'Status', value: 'Qualified' },
            ].map((stat) => (
              <div key={stat.label}>
                <p className="text-xs text-zinc-600 mb-1">{stat.label}</p>
                <p className="text-sm font-semibold text-white">{stat.value}</p>
              </div>
            ))}
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
};
