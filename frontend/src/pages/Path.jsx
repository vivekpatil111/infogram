import React, { useEffect, useState } from 'react';
import { Check, Lock, Pencil, Play, Route, Trash2 } from 'lucide-react';
import { avatarOf, deletePath, fetchPath } from '../api';
import { useApp } from '../context';
import { PathEditor } from '../components/PathEditor';
import { VerifiedBadge, useVerticals } from '../components/Knowledge';
import { Spinner } from '../components/Skeleton';

// A Learning Path: ordered lessons, your progress, and Start / Continue.
export function PathPage({ pathId }) {
  const { currentUser, openPost, openProfile, openSheet, navigate, showToast } = useApp();
  const verticals = useVerticals();
  const [path, setPath] = useState(null);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(false);
  const load = () => fetchPath(pathId).then(setPath).catch((requestError) => setError(requestError.status === 404 ? "This path isn't available." : requestError.message));
  useEffect(() => { load(); }, [pathId]); // eslint-disable-line react-hooks/exhaustive-deps
  // Progress changes as lessons are watched; refresh when the tab regains focus.
  useEffect(() => {
    const refresh = () => { if (document.visibilityState === 'visible') load(); };
    window.addEventListener('focus', refresh);
    return () => window.removeEventListener('focus', refresh);
  }, [pathId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <section className="path-page"><div className="empty-state"><b>{error}</b><p>It may have been deleted, or the creator is private.</p></div></section>;
  if (!path) return <section className="path-page"><div className="center-spinner"><Spinner/></div></section>;

  const own = path.creator.id === currentUser?.id;
  const ids = path.lessons.map((lesson) => lesson.id);
  const seen = new Set(path.lessons.filter((lesson) => lesson.seenByMe).map((lesson) => lesson.id));
  const vertical = verticals.find((item) => item.slug === path.vertical);
  const percent = path.progress.total ? Math.round((path.progress.seen / path.progress.total) * 100) : 0;
  const play = (index) => openPost(path.lessons[index], { lesson: { pathId: path.id, title: path.title, ids, index } });
  const startIndex = Math.max(0, ids.indexOf(path.next_post_id));
  const remove = () => openSheet([{ label: 'Delete path', danger: true, onClick: async () => {
    try { await deletePath(path.id); showToast('Path deleted'); navigate('Profile', { username: currentUser.username, tab: 'paths' }); } catch (requestError) { showToast(requestError.message); }
  } }], 'Delete this path? The posts stay on your profile.');

  return <section className="path-page">
    <header className="path-hero">
      <span className="path-hero-icon"><Route/></span>
      <div className="path-hero-copy">
        {vertical && <button className="vertical-pill" onClick={() => navigate('Explore', { vertical: vertical.slug })}>{vertical.emoji} {vertical.name}</button>}
        <h1>{path.title}</h1>
        <button className="path-creator" onClick={() => openProfile(path.creator.username)}>
          <img src={avatarOf(path.creator)} alt=""/><b>{path.creator.username}</b><VerifiedBadge verified={path.creator.is_verified} title={path.creator.expert_title}/>
        </button>
        {path.description && <p>{path.description}</p>}
        {!path.locked && path.progress.total > 0 && <div className="path-progress" aria-label={`${path.progress.seen} of ${path.progress.total} lessons seen`}>
          <div><i style={{ width: `${percent}%` }}/></div><span>{path.progress.seen}/{path.progress.total} lessons · {percent}%</span>
        </div>}
        <div className="path-actions">
          {!path.locked && ids.length > 0 && <button className="path-start" onClick={() => play(startIndex)}><Play fill="currentColor"/>{path.progress.seen === 0 ? 'Start path' : path.next_post_id ? 'Continue' : 'Watch again'}</button>}
          {own && <><button onClick={() => setEditing(true)}><Pencil/>Edit</button><button className="danger" onClick={remove}><Trash2/>Delete</button></>}
        </div>
      </div>
    </header>
    {path.locked
      ? <div className="private-profile-notice"><Lock/><b>This path is private</b><p>Follow {path.creator.username} to see its {path.lesson_count} lessons.</p></div>
      : <ol className="lesson-list">{path.lessons.map((lesson, index) => <li key={lesson.id}>
        <button onClick={() => play(index)} className={seen.has(lesson.id) ? 'is-seen' : ''}>
          <span className="lesson-number">{seen.has(lesson.id) ? <Check/> : index + 1}</span>
          <span className="lesson-thumb">{lesson.mediaType === 'video' && !lesson.poster ? <video src={lesson.image} muted preload="metadata"/> : <img src={lesson.poster || lesson.image} alt="" loading="lazy"/>}</span>
          <span className="lesson-copy"><b>{lesson.caption.split('\n')[0].slice(0, 90) || `Lesson ${index + 1}`}</b><small>{lesson.mediaType === 'video' ? 'Video' : lesson.mediaType === 'carousel' ? 'Carousel' : 'Post'} · {lesson.time}{lesson.resources.length ? ` · ${lesson.resources.length} resources` : ''}</small></span>
        </button>
      </li>)}</ol>}
    {!path.locked && !ids.length && <div className="empty-state"><b>No lessons yet</b>{own && <p>Edit the path to add your posts.</p>}</div>}
    {editing && <PathEditor path={path} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); load(); }}/>}
  </section>;
}
