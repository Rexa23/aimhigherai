'use client';

import React from 'react';
import { ArrowUpRight, BookOpen, Globe, Send, Twitter } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { motion } from 'framer-motion';

type Resource = {
  name: string;
  description: string;
  url: string;
  icon: LucideIcon;
};

const resources: Resource[] = [
  {
    name: 'Website',
    description: 'Explore the official AimHigher product experience.',
    url: 'https://www.aimhigher.gg/',
    icon: Globe,
  },
  {
    name: 'Docs',
    description: 'Read product docs, workflows, and integration details.',
    url: 'https://aimhigher.gitbook.io/product-docs/',
    icon: BookOpen,
  },
  {
    name: 'X',
    description: 'Follow launches, updates, and ecosystem announcements.',
    url: 'https://x.com/aimhigher_gg',
    icon: Twitter,
  },
  {
    name: 'Telegram',
    description: 'Join the community channel and connect with the team.',
    url: 'https://t.me/aimhighercommunity',
    icon: Send,
  },
];

function ResourceCard({ resource, index }: { resource: Resource; index: number }) {
  const Icon = resource.icon;

  return (
    <motion.li
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.28, delay: index * 0.06, ease: 'easeOut' }}
      className="list-none"
    >
      <article className="group h-full rounded-xl border border-white/10 bg-white/[0.02] p-5 transition-all duration-300 hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.035] hover:shadow-[0_10px_36px_rgba(0,0,0,0.28)]">
        <div className="mb-4 inline-flex h-9 w-9 items-center justify-center rounded-md border border-white/10 bg-black/35 text-zinc-200 transition-colors duration-300 group-hover:text-[#86efac]">
          <Icon className="h-4 w-4" strokeWidth={1.8} />
        </div>

        <h3 className="mb-2 text-sm font-semibold tracking-tight text-zinc-100">{resource.name}</h3>
        <p className="mb-5 min-h-[44px] text-xs leading-relaxed text-zinc-400">{resource.description}</p>

        <a
          href={resource.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-white/12 bg-white/[0.02] px-3 py-2 text-xs font-medium text-zinc-100 transition-all duration-300 hover:border-[#22c55e]/50 hover:bg-[#22c55e]/10 hover:text-white"
        >
          Open Resource
          <ArrowUpRight className="h-3.5 w-3.5" />
        </a>
      </article>
    </motion.li>
  );
}

export function ProjectDetails() {
  return (
    <section aria-labelledby="project-links-title" className="px-4 py-16 sm:px-8 sm:py-20">
      <div className="mx-auto w-full max-w-6xl">
        <header className="mx-auto mb-10 max-w-2xl text-center sm:mb-12">
          <p className="landing-eyebrow mb-3">Project Links</p>
          <h2 id="project-links-title" className="landing-title text-3xl sm:text-4xl">
            Community Resources
          </h2>
          <p className="landing-subtitle mt-4 text-base sm:text-lg">
            Direct access to the official AimHigher destination points.
          </p>
        </header>

        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 lg:gap-5">
          {resources.map((resource, index) => (
            <ResourceCard key={resource.name} resource={resource} index={index} />
          ))}
        </ul>

        <div className="mt-8 text-center sm:mt-10">
          <p className="text-xs text-zinc-500 sm:text-sm">
            Official links only. Secure external navigation enabled on every resource.
          </p>
        </div>
      </div>
    </section>
  );
}
