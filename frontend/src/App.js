import React from 'react';
import Reel from './components/Reel';
import Navbar from './components/Navbar';

const MOCK_REELS = [
  {
    id: 1,
    videoUrl: 'https://assets.mixkit.co/videos/preview/mixkit-girl-in-neon-light-1232-large.mp4',
    username: 'legal_expert_in',
    caption: 'How to register your startup in India in 5 minutes! 🇮🇳 #Startups #LegalTips',
    resources: [
      { label: 'MCA Registration Portal', url: 'https://mca.gov.in' },
      { label: 'Startup India Guide PDF', url: '#' },
      { label: 'Document Checklist', url: '#' },
    ],
  },
  {
    id: 2,
    videoUrl: 'https://assets.mixkit.co/videos/preview/mixkit-young-woman-talking-to-camera-in-a-modern-office-41543-large.mp4',
    username: 'code_master_zero',
    caption: 'Stop using for-loops for everything. Try .map() and .filter()! 💻 #Coding #ReactJS',
    resources: [
      { label: 'MDN Web Docs: Array.map', url: 'https://developer.mozilla.org' },
      { label: 'Best JS Patterns 2024', url: '#' },
    ],
  },
  {
    id: 3,
    videoUrl: 'https://assets.mixkit.co/videos/preview/mixkit-woman-working-on-her-laptop-in-a-cafe-42547-large.mp4',
    username: 'finance_pro_tips',
    caption: 'The 50-30-20 Rule for saving money. Start now! 💰 #Finance #SavingTips',
    resources: [
      { label: 'Budget Calculator Tool', url: '#' },
      { label: 'Investment Guide for Beginners', url: '#' },
    ],
  },
];

function App() {
  return (
    <div className="relative bg-black min-h-screen flex justify-center">
      {/* Reels Feed */}
      <div className="reel-container w-full max-w-md">
        {MOCK_REELS.map(reel => (
          <Reel key={reel.id} {...reel} />
        ))}
      </div>

      {/* Bottom Nav */}
      <Navbar />
    </div>
  );
}

export default App;
