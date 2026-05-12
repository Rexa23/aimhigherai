'use client';

import React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { motion } from 'framer-motion';

const footerSections = [
  {
    title: 'Product',
    links: [
      { label: 'Platform', href: '#platform' },
      { label: 'Pipeline', href: '#pipeline' },
      { label: 'Agents', href: '#agents' },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'About', href: '#' },
      { label: 'Blog', href: '#' },
      { label: 'Contact', href: '#' },
    ],
  },
  {
    title: 'Legal',
    links: [
      { label: 'Privacy', href: '#' },
      { label: 'Terms', href: '#' },
      { label: 'Security', href: '#' },
    ],
  },
];

export const Footer: React.FC = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="landing-shell border-t border-white/8">
      <div className="mx-auto w-full max-w-6xl px-8">
        {/* Top Section */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          viewport={{ once: true }}
          className="grid grid-cols-1 md:grid-cols-[1fr_2fr] gap-16 py-12"
        >
          {/* Brand */}
          <div>
            <div className="mb-3">
              <Image
                src="/logo.png"
                alt="AimHigherAI Logo"
                width={140}
                height={40}
                priority
                className="object-contain"
              />
            </div>
            <p className="text-sm text-zinc-500 leading-relaxed">
              Autonomous agents for Web3 growth. Discover, qualify, and partner with precision.
            </p>
          </div>

          {/* Links */}
          <div className="grid grid-cols-3 gap-8">
            {footerSections.map((section) => (
              <div key={section.title}>
                <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-4">
                  {section.title}
                </h4>
                <ul className="space-y-2.5">
                  {section.links.map((link) => (
                    <li key={link.label}>
                      <a href={link.href} className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors">
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Divider */}
        <div className="border-t border-white/8" />

        {/* Bottom */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ duration: 0.4 }}
          viewport={{ once: true }}
          className="flex flex-col md:flex-row md:items-center md:justify-between gap-6 py-8 text-xs text-zinc-600"
        >
          <p>© {currentYear} AimHigher AI. All rights reserved.</p>
          <div className="flex items-center gap-6">
            {['X', 'Discord', 'GitHub'].map((social) => (
              <a key={social} href="#" className="hover:text-zinc-400 transition-colors">
                {social}
              </a>
            ))}
          </div>
        </motion.div>
      </div>
    </footer>
  );
};
