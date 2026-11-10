import React, { useState } from 'react';
import { fetchReelsPage } from '../api';
import { useApp } from '../context';
import { useInfiniteList } from '../hooks';
import { ReelCard } from '../components/ReelCard';
import { Spinner } from '../components/Skeleton';

export function ReelsPage() {
  const { openCreate } = useApp();
  const [feed, setFeed] = useState('for_you');
  const reels = useInfiniteList((cursor) => fetchReelsPage(feed, cursor), [feed]);
  const items = reels.items || [];
  const drop = (reel) => reels.setItems((current) => current.filter((item) => item.id !== reel.id));
  return <section className="reels-page">
    <header className="reels-header"><b>Reels</b><div>
      <button className={feed === 'for_you' ? 'active-tab' : ''} onClick={() => setFeed('for_you')}>For You</button>
      <button className={feed === 'following' ? 'active-tab' : ''} onClick={() => setFeed('following')}>Following</button>
    </div></header>
    <div className="reels-scroller">
      {reels.items === null && <div className="reel-card skeleton"/>}
      {reels.items !== null && !items.length && <div className="empty-state reels-empty">
        <b>{feed === 'following' ? 'No reels from people you follow yet' : 'No reels yet'}</b>
        <p>Short videos that teach something show up here.</p><button onClick={() => openCreate('reel')}>Create a reel</button>
      </div>}
      {items.map((reel) => <ReelCard key={reel.id} reel={reel} onHidden={drop}/>)}
      {reels.error && <div className="empty-state"><p>{reels.error}</p><button onClick={reels.reload}>Try again</button></div>}
      <div ref={reels.sentinelRef} className="scroll-sentinel">{reels.loading && reels.items !== null ? <Spinner/> : ''}</div>
    </div>
  </section>;
}
