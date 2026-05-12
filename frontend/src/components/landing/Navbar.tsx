'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';
import { Menu, X } from 'lucide-react';

const navItems = [
  { label: 'Platform', href: '#platform' },
  { label: 'Agents', href: '#agents' },
  { label: 'Analytics', href: '#analytics' },
];

export const Navbar: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [hasPngLogo, setHasPngLogo] = useState(false);

  useEffect(() => {
    let mounted = true;
    // Check if custom logo exists in public folder without throwing
    fetch('/logo.png', { method: 'HEAD' })
      .then((res) => {
        if (!mounted) return;
        setHasPngLogo(res.ok);
      })
      .catch(() => {
        if (!mounted) return;
        setHasPngLogo(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <motion.nav
      className="fixed top-0 w-full z-50 border-b border-white/8 bg-black/50 backdrop-blur-md"
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
    >
      <div className="mx-auto flex h-14 w-full max-w-7xl items-center justify-between px-8">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 group">
          <motion.div whileHover={{ scale: 1.02 }} transition={{ duration: 0.15 }} className="relative h-7 w-7">
            <Image
              src={hasPngLogo ? '/logo.png' : '/aimhigher-logo.svg'}
              alt="AimHigher"
              width={28}
              height={28}
              priority
              className="h-full w-full"
            />
          </motion.div>
          <span className="text-sm font-semibold text-white">AimHigher</span>
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden items-center gap-8 md:flex">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="text-sm text-zinc-400 transition-colors duration-200 hover:text-zinc-200"
            >
              {item.label}
            </a>
          ))}
        </div>

        {/* CTA Buttons */}
        <div className="flex items-center gap-3">
          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
            className="landing-btn-primary rounded-md px-4 py-2 text-xs font-semibold transition-all hidden sm:block"
          >
            Get Started
          </motion.button>

          {/* Mobile Menu Toggle */}
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setIsOpen(!isOpen)}
            className="md:hidden p-2 text-zinc-400 hover:text-zinc-200"
          >
            {isOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </motion.button>
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="md:hidden border-t border-white/8 bg-black/70 backdrop-blur-md"
          >
            <div className="flex flex-col gap-1 px-8 py-4">
              {navItems.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  className="px-2 py-2 text-sm text-zinc-400 transition-colors hover:text-zinc-200"
                  onClick={() => setIsOpen(false)}
                >
                  {item.label}
                </a>
              ))}
              <button className="landing-btn-primary rounded-md px-4 py-2 text-sm font-semibold mt-2">
                Get Started
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  );
};
