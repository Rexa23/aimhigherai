'use client';

import React from 'react';
import { Navbar } from '@/components/landing/Navbar';
import { Hero } from '@/components/landing/Hero';
import { PipelineBoard } from '@/components/landing/PipelineBoard';
import { AgentNetwork } from '@/components/landing/AgentNetwork';
import { ConversationPreview } from '@/components/landing/ConversationPreview';
import { AnalyticsPanel } from '@/components/landing/AnalyticsPanel';
import { CTASection } from '@/components/landing/CTASection';
import { Footer } from '@/components/landing/Footer';
import { ProjectDetails } from '@/components/landing/ProjectDetails';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-black text-white">
      <Navbar />
      <Hero />
      <PipelineBoard />
      <AgentNetwork />
      <ConversationPreview />
      <AnalyticsPanel />
      <CTASection />
      <ProjectDetails />
      <Footer />
    </div>
  );
}
