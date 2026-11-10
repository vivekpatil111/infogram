import React, { useEffect, useState } from 'react';
import { ArrowDown, ArrowUp, X } from 'lucide-react';
import { fetchProfile, savePath } from '../api';
import { useApp } from '../context';
import { useVerticals } from './Knowledge';
import { ListSkeleton } from './Skeleton';

const MAX_LESSONS = 30;

// Create or edit a Learning Path: title, vertical, and an ordered pick of your posts.
export function PathEditor({ path = null, onClose, onSaved }) {
  const { currentUser, showToast } = useApp();
  const verticals = useVerticals();
  const [title, setTitle] = useState(path?.title || '');
  const [description, setDescription] = useState(path?.description || '');
  const [vertical, setVertical] = useState(path?.vertical || '');
  const [order, setOrder] = useState(path ? path.lessons.map((lesson) => lesson.id) : []);
  const [posts, setPosts] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    Promise.all([fetchProfile(currentUser.username, 'posts'), fetchProfile(currentUser.username, 'reels')])
      .then(([grid, reels]) => {
        const seen = new Set();
        setPosts([...grid.items, ...reels.items].filter((post) => !seen.has(post.id) && seen.add(post.id)));
      })
      .catch((requestError) => { setError(requestError.message); setPosts([]); });
  }, [currentUser.username]);

  const toggle = (id) => setOrder((current) => (current.includes(id) ? current.filter((item) => item !== id)
    : current.length >= MAX_LESSONS ? current : [...current, id]));
  const move = (index, delta) => setOrder((current) => {
    const next = [...current];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    return next;
  });
  const byId = Object.fromEntries((posts || []).map((post) => [post.id, post]));
  const save = async (event) => {
    event.preventDefault();
    if (busy) return;
    if (!title.trim()) { setError('Give the path a title.'); return; }
    if (!order.length) { setError('Pick at least one of your posts.'); return; }
    setBusy(true);
    setError('');
    try {
      const saved = await savePath({ title: title.trim(), description: description.trim(), vertical, post_ids: order }, path?.id);
      showToast(path ? 'Path updated' : 'Path created');
      onSaved(saved);
    } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  };

  return <div className="modal-backdrop create-backdrop" onClick={onClose}><section className="create-sheet path-editor" onClick={(event) => event.stopPropagation()}>
    <header><b>{path ? 'Edit path' : 'New learning path'}</b><button onClick={onClose} aria-label="Close path editor"><X/></button></header>
    <form className="create-form" onSubmit={save}>
      <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder='Title, e.g. "Mastering Startup Law"' maxLength="80" aria-label="Path title"/>
      <textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What will people learn? (optional)" rows="2" maxLength="500"/>
      <div className="vertical-picker" role="radiogroup" aria-label="Knowledge Vertical">
        {verticals.map((item) => <button type="button" key={item.slug} role="radio" aria-checked={vertical === item.slug} className={vertical === item.slug ? 'active' : ''}
          onClick={() => setVertical(vertical === item.slug ? '' : item.slug)}>{item.emoji} {item.name}</button>)}
      </div>
      {order.length > 0 && <ol className="path-order">{order.map((id, index) => <li key={id}>
        <span className="lesson-number">{index + 1}</span>
        <span className="path-order-copy">{byId[id]?.caption.slice(0, 60) || `Post ${id}`}</span>
        <button type="button" onClick={() => move(index, -1)} disabled={index === 0} aria-label="Move up"><ArrowUp/></button>
        <button type="button" onClick={() => move(index, 1)} disabled={index === order.length - 1} aria-label="Move down"><ArrowDown/></button>
        <button type="button" onClick={() => toggle(id)} aria-label="Remove from path"><X/></button>
      </li>)}</ol>}
      <p className="path-pick-hint">Tap your posts in the order people should see them ({order.length}/{MAX_LESSONS}).</p>
      {posts === null ? <ListSkeleton rows={2}/> : !posts.length ? <p className="path-pick-hint">Share some posts first, then group them into a path.</p>
        : <div className="path-pick-grid">{posts.map((post) => {
          const position = order.indexOf(post.id);
          return <button type="button" key={post.id} className={position >= 0 ? 'picked' : ''} onClick={() => toggle(post.id)} aria-pressed={position >= 0} aria-label={`Lesson: ${post.caption.slice(0, 40) || post.id}`}>
            {post.mediaType === 'video' && !post.poster ? <video src={post.image} muted preload="metadata"/> : <img src={post.poster || post.image} alt="" loading="lazy"/>}
            {position >= 0 && <i>{position + 1}</i>}
          </button>;
        })}</div>}
      {error && <p className="auth-error" role="alert">{error}</p>}
      <div className="create-footer"><span>{busy ? 'Saving…' : 'Only your own posts can be lessons'}</span><button disabled={busy}>{busy ? 'Please wait…' : path ? 'Save' : 'Create path'}</button></div>
    </form>
  </section></div>;
}
