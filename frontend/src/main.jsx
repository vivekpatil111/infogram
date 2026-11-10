import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './index.css';
// dark.css (generated) loads before polish.css so the hand-tuned dark rules
// at the end of polish.css win over generated ones of equal specificity.
import './dark.css';
import './polish.css';

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);

// Installable app: offline shell + cached assets (production builds only, so
// the dev server never serves stale modules).
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
}
