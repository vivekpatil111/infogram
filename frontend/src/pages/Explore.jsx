import React, { useEffect, useState } from 'react';
import { Clapperboard, Heart, Layers, MessageCircle, Search } from 'lucide-react';
import { fetchExplorePage, fetchTopics, formatCount } from '../api';
import { useApp } from '../context';
import { useInfiniteList } from '../hooks';

export function ExplorePage({ topic = '' }) {
  const { openPost, navigate, openSearch } = useApp();
  const [topics, setTopics] = useState([]);
  const explore = useInfiniteList((cursor) => fetchExplorePage(topic, cursor), [topic]);
  useEffect(() => { fetchTopics().then(setTopics).catch(() => setTopics([])); }, []);
  const items = explore.items || [];
  const drop = (post) => explore.setItems((current) => current.filter((item) => item.id !== post.id));
  return <section className="explore-page">
    <header className="explore-heading">
      <div><h1>{topic ? topic : 'Explore'}</h1><p>{topic ? (topic.startsWith('#') ? 'Posts with this hashtag' : 'Posts on this topic') : 'Discover ideas, people and knowledge'}</p></div>
      <button className="explore-search" onClick={openSearch}><Search/>Search</button>
    </header>
    {topics.length > 0 && <div className="topic-chips">
      <button className={!topic ? 'active' : ''} onClick={() => navigate('Explore', { topic: '' })}>For you</button>
      {topics.map((name) => <button key={name} className={topic === name ? 'active' : ''} onClick={() => navigate('Explore', { topic: name })}>{name}</button>)}
    </div>}
    {explore.items === null && <div className="explore-grid">{Array.from({ length: 6 }, (_, i) => <div key={i} className="explore-tile skeleton"/>)}</div>}
    {explore.items !== null && !items.length && <div className="empty-state"><b>Nothing here yet</b><p>{topic ? 'No posts match this yet.' : "You've seen everything from creators you don't follow. Check back soon."}</p></div>}
    <div className="explore-grid">{items.map((post, index) => <button className={`explore-tile ${index % 10 === 4 ? 'tall' : ''}`} key={post.id} onClick={() => openPost(post, { onDeleted: drop })}>
      {post.mediaType === 'video' && !post.poster ? <video src={post.image} muted preload="metadata"/> : <img src={post.poster || post.image} alt={post.caption.slice(0, 80)} loading="lazy"/>}
      {post.mediaType === 'video' && <Clapperboard className="tile-badge"/>}
      {post.mediaType === 'carousel' && <Layers className="tile-badge"/>}
      <span className="tile-stats"><span><Heart fill="currentColor"/>{formatCount(post.likeCount)}</span><span><MessageCircle fill="currentColor"/>{formatCount(post.commentCount)}</span></span>
    </button>)}</div>
    {explore.error && <div className="empty-state"><p>{explore.error}</p><button onClick={explore.reload}>Try again</button></div>}
    <div ref={explore.sentinelRef} className="scroll-sentinel">{explore.loading && explore.items !== null ? 'Loading more…' : ''}</div>
  </section>;
}
