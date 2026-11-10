import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { BadgeCheck, CheckSquare, ExternalLink, FileText, Lightbulb, Route, Square, X } from 'lucide-react';
import { fetchVerticals, markSeen, openResource } from '../api';
import { useApp } from '../context';
import { readStored, writeStored } from '../hooks';

// ---- Expert badge ----------------------------------------------------------
export function VerifiedBadge({ verified, title }) {
  if (!verified) return null;
  const label = title ? `Verified expert · ${title}` : 'Verified expert';
  return <span className="verified-badge" title={label} aria-label={label} role="img"><BadgeCheck/></span>;
}

// ---- Knowledge Verticals -----------------------------------------------------
export function useVerticals() {
  const [verticals, setVerticals] = useState([]);
  useEffect(() => { fetchVerticals().then(setVerticals).catch(() => setVerticals([])); }, []);
  return verticals;
}

export function VerticalPill({ slug }) {
  const { navigate } = useApp();
  const vertical = useVerticals().find((item) => item.slug === slug);
  if (!vertical) return null;
  return <button className="vertical-pill" onClick={() => navigate('Explore', { vertical: slug })}>{vertical.emoji} {vertical.name}</button>;
}

// ---- Learning Path membership chip -------------------------------------------
export function PathChip({ paths }) {
  const { navigate } = useApp();
  if (!paths?.length) return null;
  const path = paths[0];
  return <button className="path-chip" onClick={() => navigate('Path', { id: path.id })}>
    <Route/><span>Part {path.position} of {path.total}</span><b>{path.title}</b>
  </button>;
}

// ---- Seen tracking -------------------------------------------------------------
// A post counts as seen after it has been at least 60% on screen for a second.
export function useSeen(ref, postId) {
  useEffect(() => {
    const element = ref.current;
    if (!element || typeof IntersectionObserver === 'undefined') return undefined;
    let timer = null;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) timer = window.setTimeout(() => { markSeen(postId); observer.disconnect(); }, 1000);
      else window.clearTimeout(timer);
    }, { threshold: 0.6 });
    observer.observe(element);
    return () => { window.clearTimeout(timer); observer.disconnect(); };
  }, [ref, postId]);
}

// ---- Resource Drawer ("Aha!" button) -------------------------------------------
const CHECK_KEY = 'infogram_checklists';
const countedThisSession = new Set();
const countOpen = (postId, resourceId) => {
  if (countedThisSession.has(resourceId)) return;
  countedThisSession.add(resourceId);
  openResource(postId, resourceId);
};

export function ResourceButton({ post, className = '' }) {
  const [open, setOpen] = useState(false);
  if (!post.resources?.length) return null;
  return <>
    <button className={`resource-button ${className}`} onClick={() => setOpen(true)} aria-label={`Resources (${post.resources.length})`}>
      <Lightbulb/><span>Resources</span><i>{post.resources.length}</i>
    </button>
    {/* Portal: feed cards animate with transform, which would trap a fixed overlay inside the card. */}
    {open && createPortal(<ResourceDrawer post={post} onClose={() => setOpen(false)}/>, document.body)}
  </>;
}

function ResourceDrawer({ post, onClose }) {
  const { currentUser } = useApp();
  const own = post.authorId === currentUser?.id;
  const [checked, setChecked] = useState(() => readStored(CHECK_KEY, {}));
  const toggle = (resourceId, index) => {
    const key = `${resourceId}:${index}`;
    const next = { ...checked, [key]: !checked[key] };
    if (!next[key]) delete next[key];
    setChecked(next);
    writeStored(CHECK_KEY, next);
  };
  useEffect(() => {
    const escape = (event) => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [onClose]);
  return <div className="modal-backdrop menu-backdrop" onClick={onClose}><section className="resource-drawer" onClick={(event) => event.stopPropagation()} role="dialog" aria-label="Resources">
    <header><span><Lightbulb/></span><div><b>Resources</b><small>From {post.name}</small></div><button onClick={onClose} aria-label="Close resources"><X/></button></header>
    <div className="resource-list">
      {post.resources.map((resource) => resource.kind === 'checklist'
        ? <div className="resource checklist" key={resource.id}>
          <div className="resource-head"><span className="resource-icon"><CheckSquare/></span><b>{resource.title}</b>
            <small>{resource.items.filter((_, i) => checked[`${resource.id}:${i}`]).length}/{resource.items.length} done</small></div>
          <ul>{resource.items.map((item, index) => <li key={index}><button onClick={() => { toggle(resource.id, index); countOpen(post.id, resource.id); }} className={checked[`${resource.id}:${index}`] ? 'done' : ''}>
            {checked[`${resource.id}:${index}`] ? <CheckSquare/> : <Square/>}<span>{item}</span></button></li>)}</ul>
        </div>
        : <a className="resource" key={resource.id} href={resource.url} target="_blank" rel="noopener noreferrer nofollow ugc" onClick={() => countOpen(post.id, resource.id)}>
          <span className="resource-icon">{resource.kind === 'pdf' ? <FileText/> : <ExternalLink/>}</span>
          <span className="resource-copy"><b>{resource.title}</b><small>{resource.kind === 'pdf' ? 'PDF guide' : hostOf(resource.url)}</small></span>
          {own && typeof resource.open_count === 'number' && <em>{resource.open_count} {resource.open_count === 1 ? 'open' : 'opens'}</em>}
        </a>)}
    </div>
    <p className="resource-note">Checklist ticks are saved on this device.</p>
  </section></div>;
}

function hostOf(url) {
  try { return new URL(url).host.replace(/^www\./, ''); } catch { return url; }
}
