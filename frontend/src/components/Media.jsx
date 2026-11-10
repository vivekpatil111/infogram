import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Heart } from 'lucide-react';

// Image, video or carousel. onDoubleTap -> like (with a heart burst).
export function MediaView({ post, className = 'post-image', onDoubleTap }) {
  const slides = post.slides?.length ? post.slides : [{ url: post.image, type: post.mediaType === 'video' ? 'video' : 'image', poster: post.poster }];
  const [index, setIndex] = useState(0);
  const [burst, setBurst] = useState(false);
  const slide = slides[Math.min(index, slides.length - 1)];
  const doubleTap = () => {
    if (!onDoubleTap) return;
    onDoubleTap();
    setBurst(true);
    window.setTimeout(() => setBurst(false), 700);
  };
  return <div className="media-frame" onDoubleClick={doubleTap}>
    {slide.type === 'video'
      ? <video key={slide.url} className={className} src={slide.url} poster={slide.poster || undefined} controls playsInline preload="metadata"/>
      : <img key={slide.url} className={className} src={slide.url} alt={post.caption ? post.caption.slice(0, 120) : `Post by ${post.name}`} loading="lazy"/>}
    {slides.length > 1 && <>
      {index > 0 && <button className="media-arrow left" onClick={() => setIndex(index - 1)} aria-label="Previous"><ChevronLeft/></button>}
      {index < slides.length - 1 && <button className="media-arrow right" onClick={() => setIndex(index + 1)} aria-label="Next"><ChevronRight/></button>}
      <div className="media-dots">{slides.map((item, dot) => <i key={item.url + dot} className={dot === index ? 'active' : ''}/>)}</div>
      <span className="media-counter">{index + 1}/{slides.length}</span>
    </>}
    {burst && <Heart className="like-burst" fill="currentColor"/>}
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
