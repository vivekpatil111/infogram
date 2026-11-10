import React, { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Heart, Play, Volume2, VolumeX } from 'lucide-react';

// Images fade in once decoded instead of popping in line by line.
export function FadeImage({ className = '', onLoad, onError, ...props }) {
  const [loaded, setLoaded] = useState(false);
  return <img {...props} className={`fade-media ${loaded ? 'is-loaded' : ''} ${className}`}
    onLoad={(event) => { setLoaded(true); onLoad?.(event); }}
    onError={(event) => { setLoaded(true); onError?.(event); }}/>;
}

// Feed/modal video: plays muted while on screen, tap to pause, corner mute toggle.
// No native controls bar over the content.
function InlineVideo({ src, poster, className }) {
  const ref = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(true);
  const [progress, setProgress] = useState(0);
  const [pausedByUser, setPausedByUser] = useState(false);
  useEffect(() => {
    const video = ref.current;
    if (!video) return undefined;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !pausedByUser) video.play().catch(() => {});
      else if (!entry.isIntersecting) video.pause();
    }, { threshold: 0.6 });
    observer.observe(video);
    return () => observer.disconnect();
  }, [pausedByUser]);
  const toggle = () => {
    const video = ref.current;
    if (!video) return;
    if (video.paused) { setPausedByUser(false); video.play().catch(() => {}); } else { setPausedByUser(true); video.pause(); }
  };
  return <div className="inline-video">
    <video ref={ref} className={className} src={src} poster={poster || undefined} muted={muted} loop playsInline preload="metadata"
      onClick={toggle} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
      onTimeUpdate={(event) => { const v = event.currentTarget; if (v.duration) setProgress(v.currentTime / v.duration); }}/>
    {!playing && <span className="inline-video-play" aria-hidden="true"><Play fill="currentColor"/></span>}
    <button className="inline-video-mute" onClick={(event) => { event.stopPropagation(); setMuted((value) => !value); }} aria-label={muted ? 'Unmute' : 'Mute'}>
      {muted ? <VolumeX/> : <Volume2/>}
    </button>
    <i className="inline-video-progress" style={{ transform: `scaleX(${progress})` }}/>
  </div>;
}

// Image, video or carousel. onDoubleTap -> like (with a heart burst).
export function MediaView({ post, className = 'post-image', onDoubleTap }) {
  const slides = post.slides?.length ? post.slides : [{ url: post.image, type: post.mediaType === 'video' ? 'video' : 'image', poster: post.poster }];
  const [index, setIndex] = useState(0);
  const [burst, setBurst] = useState(0);
  const slide = slides[Math.min(index, slides.length - 1)];
  const touchStart = useRef(null);
  const go = (next) => setIndex(Math.max(0, Math.min(slides.length - 1, next)));
  // Horizontal swipe on touch screens moves between slides.
  const onTouchStart = (event) => { touchStart.current = event.touches[0].clientX; };
  const onTouchEnd = (event) => {
    if (touchStart.current === null || slides.length < 2) return;
    const dx = event.changedTouches[0].clientX - touchStart.current;
    touchStart.current = null;
    if (Math.abs(dx) > 40) go(index + (dx < 0 ? 1 : -1));
  };
  const doubleTap = () => {
    if (!onDoubleTap) return;
    onDoubleTap();
    setBurst((value) => value + 1);
  };
  useEffect(() => {
    if (!burst) return undefined;
    const timer = window.setTimeout(() => setBurst(0), 800);
    return () => window.clearTimeout(timer);
  }, [burst]);
  return <div className="media-frame" onDoubleClick={doubleTap} onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
    {slide.type === 'video'
      ? <InlineVideo key={slide.url} className={className} src={slide.url} poster={slide.poster}/>
      : <FadeImage key={slide.url} className={className} src={slide.url} alt={post.caption ? post.caption.slice(0, 120) : `Post by ${post.name}`} loading="lazy" decoding="async"/>}
    {slides.length > 1 && <>
      {index > 0 && <button className="media-arrow left" onClick={() => go(index - 1)} aria-label="Previous"><ChevronLeft/></button>}
      {index < slides.length - 1 && <button className="media-arrow right" onClick={() => go(index + 1)} aria-label="Next"><ChevronRight/></button>}
      <div className="media-dots">{slides.map((item, dot) => <button type="button" key={item.url + dot} className={dot === index ? 'active' : ''} onClick={() => go(dot)} aria-label={`Go to slide ${dot + 1}`}/>)}</div>
      <span className="media-counter">{index + 1}/{slides.length}</span>
    </>}
    {burst > 0 && <Heart key={burst} className="like-burst" fill="currentColor"/>}
  </div>;
}

// Caption with tappable #hashtags.
export function Caption({ text, onHashtag }) {
  if (!text) return null;
  const parts = text.split(/(#[\p{L}\p{N}_]+)/u);
  return <>{parts.map((part, i) => (part.startsWith('#') && onHashtag
    ? <button key={i} className="hashtag-link" onClick={() => onHashtag(part.slice(1).toLowerCase())}>{part}</button>
    : <React.Fragment key={i}>{part}</React.Fragment>))}</>;
}
