import React, { useEffect, useRef, useState } from 'react';
import { Bookmark, Heart, MessageCircle, MoreHorizontal, Send, Volume2, VolumeX } from 'lucide-react';
import { formatCount, postLink } from '../api';
import { useApp } from '../context';
import { usePostEngagement } from './postActions';
import { FollowButton } from './Sheets';
import { ResourceButton, VerifiedBadge } from './Knowledge';

export function ReelCard({ reel, onHidden }) {
  const { currentUser, openProfile, openPost, openShare, openSheet, openReport, openAbout, showToast } = useApp();
  const { liked, likeCount, saved, toggleLike, toggleSave } = usePostEngagement(reel);
  const videoRef = useRef(null);
  const [muted, setMuted] = useState(true);
  const [flash, setFlash] = useState(0);
  const [burst, setBurst] = useState(0);
  const toggleMute = () => { setMuted((current) => !current); setFlash((value) => value + 1); };
  const doubleTapLike = () => { toggleLike(true); setBurst((value) => value + 1); };
  const [commentCount, setCommentCount] = useState(reel.commentCount);
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) video.play().catch(() => {}); else video.pause();
    }, { threshold: 0.7 });
    observer.observe(video);
    return () => observer.disconnect();
  }, []);
  const own = reel.authorId === currentUser?.id;
  const menu = () => openSheet([
    { label: 'Report', danger: true, hidden: own, onClick: () => openReport({ type: 'post', id: reel.id, name: reel.name }, () => onHidden?.(reel)) },
    { label: 'Not interested', hidden: own, onClick: () => { onHidden?.(reel); showToast("We'll show fewer reels like this"); } },
    { label: 'Go to post', onClick: () => openPost(reel) },
    { label: 'About this account', hidden: own, onClick: () => openAbout(reel.name) },
    { label: 'Copy link', onClick: () => { navigator.clipboard?.writeText(postLink(reel.id)); showToast('Link copied'); } },
  ]);
  return <article className="reel-card">
    <video ref={videoRef} className="reel-video" src={reel.image} poster={reel.poster || undefined} muted={muted} loop playsInline preload="metadata" onClick={toggleMute} onDoubleClick={doubleTapLike}/>
    <div className="reel-shade"/>
    <div className="reel-topline"><span/><button onClick={toggleMute} aria-label={muted ? 'Unmute reel' : 'Mute reel'}>{muted ? <VolumeX/> : <Volume2/>}</button></div>
    {flash > 0 && <span key={flash} className="reel-flash" aria-hidden="true">{muted ? <VolumeX/> : <Volume2/>}</span>}
    {burst > 0 && <Heart key={`b${burst}`} className="like-burst" fill="currentColor"/>}
    <div className="reel-copy">
      {reel.place && <span className="reel-topic">{reel.place}</span>}
      <div className="reel-profile">
        <button className="avatar-button" onClick={() => openProfile(reel.name)}><img src={reel.avatar} alt=""/></button>
        <b role="button" tabIndex={0} onClick={() => openProfile(reel.name)}>{reel.name}<VerifiedBadge verified={reel.verified} title={reel.expertTitle}/></b>
        {(reel.followStatus === 'none' || reel.followStatus === 'requested') && <FollowButton name={reel.name} initialStatus={reel.followStatus} className="reel-follow"/>}
      </div>
      {reel.caption && <p>{reel.caption}</p>}
      <ResourceButton post={reel} className="on-dark"/>
    </div>
    <div className="reel-actions">
      <button className={liked ? 'reel-liked' : ''} onClick={() => toggleLike()} aria-label={liked ? 'Unlike' : 'Like'}><Heart fill={liked ? 'currentColor' : 'none'}/><span>{formatCount(likeCount)}</span></button>
      <button onClick={() => openPost(reel, { onCommentAdded: () => setCommentCount((count) => count + 1) })} aria-label="Comments"><MessageCircle/><span>{formatCount(commentCount)}</span></button>
      <button onClick={() => openShare(reel)} aria-label="Share"><Send/><span>Share</span></button>
      <button className={saved ? 'reel-saved' : ''} onClick={toggleSave} aria-label={saved ? 'Remove from saved' : 'Save'}><Bookmark fill={saved ? 'currentColor' : 'none'}/><span>{saved ? 'Saved' : 'Save'}</span></button>
      <button onClick={menu} aria-label="More options"><MoreHorizontal/></button>
    </div>
  </article>;
}
