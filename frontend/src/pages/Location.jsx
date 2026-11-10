import React, { useState } from 'react';
import { Clapperboard, Heart, Layers, MapPin, MessageCircle } from 'lucide-react';
import { fetchLocationPage, formatCount } from '../api';
import { useApp } from '../context';
import { useInfiniteList } from '../hooks';
import { FadeImage } from '../components/Media';
import { Spinner } from '../components/Skeleton';

// A place's page: every visible post tagged there, newest first.
export function LocationPage({ slug }) {
  const { openPost } = useApp();
  const [location, setLocation] = useState(null);
  const posts = useInfiniteList(async (cursor) => {
    const page = await fetchLocationPage(slug, cursor);
    setLocation(page.location);
    return page;
  }, [slug]);
  const items = posts.items || [];
  const drop = (post) => posts.setItems((current) => current.filter((item) => item.id !== post.id));
  const notFound = posts.error && /not found/i.test(posts.error);

  return <section className="explore-page location-page">
    <header className="location-heading">
      <span className="location-icon"><MapPin/></span>
      <div>
        <h1>{location?.name || (notFound ? 'Location not found' : ' ')}</h1>
        <p>{location ? `${formatCount(location.post_count)} ${location.post_count === 1 ? 'post' : 'posts'}` : notFound ? 'This place has no posts.' : ''}</p>
      </div>
    </header>
    {posts.items === null && !posts.error && <div className="explore-grid">{Array.from({ length: 6 }, (_, i) => <div key={i} className="explore-tile skeleton"/>)}</div>}
    {posts.items !== null && !items.length && !posts.error && <div className="empty-state"><b>No posts here yet</b><p>Posts tagged with this place will show up here.</p></div>}
    <div className="explore-grid">{items.map((post, index) => <button className="explore-tile" key={post.id} style={{ '--i': index % 12 }} onClick={() => openPost(post, { onDeleted: drop })}>
      {post.mediaType === 'video' && !post.poster ? <video src={post.image} muted preload="metadata"/> : <FadeImage src={post.poster || post.image} alt={post.caption.slice(0, 80)} loading="lazy" decoding="async"/>}
      {post.mediaType === 'video' && <Clapperboard className="tile-badge"/>}
      {post.mediaType === 'carousel' && <Layers className="tile-badge"/>}
      <span className="tile-stats"><span><Heart fill="currentColor"/>{formatCount(post.likeCount)}</span><span><MessageCircle fill="currentColor"/>{formatCount(post.commentCount)}</span></span>
    </button>)}</div>
    {posts.error && !notFound && <div className="empty-state"><p>{posts.error}</p><button onClick={posts.reload}>Try again</button></div>}
    <div ref={posts.sentinelRef} className="scroll-sentinel">{posts.loading && posts.items !== null ? <Spinner/> : ''}</div>
  </section>;
}
