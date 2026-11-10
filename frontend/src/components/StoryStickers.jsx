import React, { useRef, useState } from 'react';
import { AtSign, BarChart3, Link2, X } from 'lucide-react';
import { voteStoryPoll } from '../api';
import { useApp } from '../context';

const DEFAULT_SPOTS = [[50, 28], [50, 52], [50, 74]];

// ---- Viewer: stickers placed on a story ----------------------------------------
export function StickerLayer({ story, onOpenProfile, onPause }) {
  const [stickers, setStickers] = useState(story.stickers);
  const [busy, setBusy] = useState(false);
  const { showToast } = useApp();
  const vote = async (option) => {
    if (busy) return;
    setBusy(true);
    onPause?.();
    try {
      const updated = await voteStoryPoll(story.id, option);
      setStickers(updated.stickers);
      story.stickers = updated.stickers; // keep the tray copy in sync
    } catch (error) { showToast(`Poll: ${error.message}`); } finally { setBusy(false); }
  };
  return <div className="sticker-layer">
    {stickers.map((sticker, index) => <div key={index} className={`story-sticker ${sticker.type}`} style={{ left: `${sticker.x}%`, top: `${sticker.y}%` }}>
      {sticker.type === 'mention' && <button onClick={() => onOpenProfile(sticker.username)}>@{sticker.username}</button>}
      {sticker.type === 'link' && <a href={sticker.url} target="_blank" rel="noopener noreferrer nofollow ugc" onClick={onPause}><Link2/>{sticker.label || hostOf(sticker.url)}</a>}
      {sticker.type === 'poll' && <PollCard poll={sticker} onVote={vote} busy={busy}/>}
    </div>)}
  </div>;
}

function PollCard({ poll, onVote, busy }) {
  const total = poll.counts ? poll.counts[0] + poll.counts[1] : 0;
  const voted = poll.my_vote !== null && poll.my_vote !== undefined;
  return <div className="poll-card">
    <b>{poll.question}</b>
    <div className="poll-options">{poll.options.map((option, index) => {
      const percent = poll.counts && total ? Math.round((poll.counts[index] / total) * 100) : 0;
      return <button key={index} disabled={busy || voted} onClick={() => onVote(index)} className={voted && poll.my_vote === index ? 'mine' : ''}>
        {poll.counts && <i style={{ width: `${percent}%` }}/>}
        <span>{option}</span>{poll.counts && <em>{percent}%</em>}
      </button>;
    })}</div>
    {poll.counts && <small>{total} {total === 1 ? 'vote' : 'votes'}</small>}
  </div>;
}

// ---- Composer: add and drag stickers on the story preview -----------------------
export function StickerComposer({ stickers, setStickers, children }) {
  const frame = useRef(null);
  const [editing, setEditing] = useState(null); // 'mention' | 'link' | 'poll'
  const [draft, setDraft] = useState({});
  const drag = useRef(null);
  const add = (sticker) => {
    const [x, y] = DEFAULT_SPOTS[stickers.length] || [50, 50];
    setStickers([...stickers, { ...sticker, x, y }]);
    setEditing(null);
    setDraft({});
  };
  const onPointerDown = (index, event) => {
    if (event.target.closest('.sticker-remove')) return;
    drag.current = index;
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };
  const onPointerMove = (event) => {
    if (drag.current === null || !frame.current) return;
    const box = frame.current.getBoundingClientRect();
    const x = Math.min(95, Math.max(5, ((event.clientX - box.left) / box.width) * 100));
    const y = Math.min(92, Math.max(6, ((event.clientY - box.top) / box.height) * 100));
    setStickers(stickers.map((item, i) => (i === drag.current ? { ...item, x: Math.round(x), y: Math.round(y) } : item)));
  };
  const hasPoll = stickers.some((item) => item.type === 'poll');
  const full = stickers.length >= 3;
  return <div className="sticker-composer">
    <div className="sticker-frame" ref={frame} onPointerMove={onPointerMove} onPointerUp={() => { drag.current = null; }} onPointerLeave={() => { drag.current = null; }}>
      {children}
      {stickers.map((sticker, index) => <div key={index} className={`story-sticker ${sticker.type} draggable`} style={{ left: `${sticker.x}%`, top: `${sticker.y}%` }} onPointerDown={(event) => onPointerDown(index, event)}>
        {sticker.type === 'mention' && <span className="sticker-chip">@{sticker.username}</span>}
        {sticker.type === 'link' && <span className="sticker-chip link"><Link2/>{sticker.label || hostOf(sticker.url)}</span>}
        {sticker.type === 'poll' && <div className="poll-card preview"><b>{sticker.question}</b><div className="poll-options">{sticker.options.map((o) => <span key={o}>{o}</span>)}</div></div>}
        <button type="button" className="sticker-remove" onClick={() => setStickers(stickers.filter((_, i) => i !== index))} aria-label="Remove sticker"><X/></button>
      </div>)}
    </div>
    <div className="sticker-tools">
      <button type="button" disabled={full} onClick={() => setEditing('mention')}><AtSign/>Mention</button>
      <button type="button" disabled={full} onClick={() => setEditing('link')}><Link2/>Link</button>
      <button type="button" disabled={full || hasPoll} onClick={() => setEditing('poll')}><BarChart3/>Poll</button>
      {stickers.length > 0 && <small>Drag stickers to place them</small>}
    </div>
    {editing && <div className="sticker-form">
      {editing === 'mention' && <input autoFocus value={draft.username || ''} onChange={(e) => setDraft({ username: e.target.value.replace(/^@/, '') })} placeholder="username" aria-label="Username to mention"/>}
      {editing === 'link' && <><input autoFocus value={draft.url || ''} onChange={(e) => setDraft({ ...draft, url: e.target.value })} placeholder="https://…" inputMode="url" aria-label="Link"/>
        <input value={draft.label || ''} onChange={(e) => setDraft({ ...draft, label: e.target.value })} placeholder="Label (optional)" maxLength="30" aria-label="Link label"/></>}
      {editing === 'poll' && <><input autoFocus value={draft.question || ''} onChange={(e) => setDraft({ ...draft, question: e.target.value })} placeholder="Ask a question…" maxLength="80" aria-label="Poll question"/>
        <div className="sticker-form-row"><input value={draft.a || ''} onChange={(e) => setDraft({ ...draft, a: e.target.value })} placeholder="Yes" maxLength="25" aria-label="First answer"/>
          <input value={draft.b || ''} onChange={(e) => setDraft({ ...draft, b: e.target.value })} placeholder="No" maxLength="25" aria-label="Second answer"/></div></>}
      <div className="sticker-form-row">
        <button type="button" className="text-button" onClick={() => { setEditing(null); setDraft({}); }}>Cancel</button>
        <button type="button" className="sticker-add" onClick={() => {
          if (editing === 'mention' && draft.username?.trim()) add({ type: 'mention', username: draft.username.trim() });
          if (editing === 'link' && draft.url?.trim()) add({ type: 'link', url: draft.url.trim(), label: (draft.label || '').trim() });
          if (editing === 'poll' && draft.question?.trim()) add({ type: 'poll', question: draft.question.trim(), options: [(draft.a || 'Yes').trim() || 'Yes', (draft.b || 'No').trim() || 'No'] });
        }}>Add</button>
      </div>
    </div>}
  </div>;
}

function hostOf(url) {
  try { return new URL(url.includes('://') ? url : `https://${url}`).host.replace(/^www\./, ''); } catch { return url; }
}
