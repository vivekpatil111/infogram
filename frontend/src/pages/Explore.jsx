import React from 'react';
import { Clapperboard, Heart, Layers, MessageCircle, Search } from 'lucide-react';
import { fetchExplorePage, formatCount } from '../api';
import { useApp } from '../context';
import { useInfiniteList } from '../hooks';
import { useVerticals } from '../components/Knowledge';
import { Spinner } from '../components/Skeleton';
import { FadeImage } from '../components/Media';

export function ExplorePage({ topic = '', vertical = '' }) {
  const { openPost, navigate, openSearch } = useApp();
  const verticals = useVerticals();
  const current = verticals.find((item) => item.slug === vertical);
  const explore = useInfiniteList((cursor) => fetchExplorePage(topic, cursor, vertical), [topic, vertical]);
  const items = explore.items || [];
  const drop = (post) => explore.setItems((current) => current.filter((item) => item.id !== post.id));
  return <section className="explore-page">
    <header className="explore-heading">
      <div><h1>{current ? `${current.emoji} ${current.name}` : topic || 'Explore'}</h1>
        <p>{current ? `${current.description}${current.expert_count ? ` · ${current.expert_count} verified ${current.expert_count === 1 ? 'expert' : 'experts'}` : ''}` : topic ? (topic.startsWith('#') ? 'Posts with this hashtag' : 'Posts on this topic') : 'Discover ideas, people and knowledge'}</p></div>
      <button className="explore-search" onClick={openSearch}><Search/>Search</button>
    </header>
    {verticals.length > 0 && <div className="topic-chips">
      <button className={!topic && !vertical ? 'active' : ''} onClick={() => navigate('Explore')}>For you</button>
      {verticals.map((item) => <button key={item.slug} className={vertical === item.slug ? 'active' : ''} onClick={() => navigate('Explore', { vertical: item.slug })}>{item.emoji} {item.name}</button>)}
    </div>}
    {explore.items === null && <div className="explore-grid">{Array.from({ length: 6 }, (_, i) => <div key={i} className="explore-tile skeleton"/>)}</div>}
    {explore.items !== null && !items.length && <div className="empty-state"><b>Nothing here yet</b><p>{topic || vertical ? 'No posts here yet. Be the first to share something useful.' : "You've seen everything from creators you don't follow. Check back soon."}</p></div>}
    <div className="explore-grid">{items.map((post, index) => <button className={`explore-tile ${post.mediaType === 'video' ? 'tall' : ''}`} style={{ '--i': index % 12 }} key={post.id} onClick={() => openPost(post, { onDeleted: drop })}>
      {post.mediaType === 'video' && !post.poster ? <video src={post.image} muted preload="metadata"/> : <FadeImage src={post.poster || post.image} alt={post.caption.slice(0, 80)} loading="lazy" decoding="async"/>}
      {post.mediaType === 'video' && <Clapperboard className="tile-badge"/>}
      {post.mediaType === 'carousel' && <Layers className="tile-badge"/>}
      <span className="tile-stats"><span><Heart fill="currentColor"/>{formatCount(post.likeCount)}</span><span><MessageCircle fill="currentColor"/>{formatCount(post.commentCount)}</span></span>
    </button>)}</div>
    {explore.error && <div className="empty-state"><p>{explore.error}</p><button onClick={explore.reload}>Try again</button></div>}
    <div ref={explore.sentinelRef} className="scroll-sentinel">{explore.loading && explore.items !== null ? <Spinner/> : ''}</div>
  </section>;
}
