import React, { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Eye, MoreHorizontal, Send, Trash2, X } from 'lucide-react';
import { createConversation, deleteStory, fetchStoryViewers, markStoryViewed, sendConversationMessage, setUserMuted } from '../api';
import { useApp } from '../context';

const IMAGE_SECONDS = 5;

// Story tray: your own ring first (or "+ Your story"), then creators.
export function StoryTray({ groups, onOpen }) {
  const { currentUser, openCreate } = useApp();
  const ownIndex = groups.findIndex((group) => group.isOwn);
  return <section className="stories">
    {ownIndex === -1 && currentUser && <button className="story" onClick={() => openCreate('story')}>
      <span className="story-ring own"><img src={currentUser.avatar} alt=""/><b>+</b></span><span>Your story</span>
    </button>}
    {groups.map((group, index) => <button className="story" key={group.authorId} onClick={() => onOpen(index)}>
      <span className={`story-ring ${group.hasUnseen ? '' : 'seen'}`}><img src={group.avatar} alt=""/></span>
      <span>{group.isOwn ? 'Your story' : group.name}</span>
    </button>)}
  </section>;
}

export function StoryViewer({ groups, startIndex, onClose, onChanged }) {
  const { currentUser, openProfile, openReport, openSheet, openCreate, showToast } = useApp();
  const [groupIndex, setGroupIndex] = useState(startIndex);
  const [storyIndex, setStoryIndex] = useState(() => groups[startIndex]?.resumeIndex || 0);
  const [paused, setPaused] = useState(false);
  const [reply, setReply] = useState('');
  const [viewers, setViewers] = useState(null);
  const [showViewers, setShowViewers] = useState(false);
  const timer = useRef(null);
  const group = groups[groupIndex];
  const story = group?.stories[Math.min(storyIndex, group.stories.length - 1)];

  const move = (direction) => {
    if (!group) return;
    const nextStory = storyIndex + direction;
    if (nextStory >= 0 && nextStory < group.stories.length) { setStoryIndex(nextStory); return; }
    const nextGroup = groupIndex + direction;
    if (nextGroup < 0 || nextGroup >= groups.length) { onClose(); return; }
    setGroupIndex(nextGroup);
    setStoryIndex(direction > 0 ? groups[nextGroup].resumeIndex || 0 : groups[nextGroup].stories.length - 1);
  };

  // Mark as seen; auto-advance photos.
  useEffect(() => {
    if (!story) return undefined;
    setViewers(null);
    setShowViewers(false);
    if (!story.viewed && !group.isOwn) {
      story.viewed = true;
      markStoryViewed(story.id).catch(() => {});
      onChanged?.();
    }
    if (group.isOwn) fetchStoryViewers(story.id).then(setViewers).catch(() => setViewers([]));
    return undefined;
  }, [story?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    window.clearTimeout(timer.current);
    if (!story || paused || story.mediaType === 'video') return undefined;
    timer.current = window.setTimeout(() => move(1), IMAGE_SECONDS * 1000);
    return () => window.clearTimeout(timer.current);
  }, [story?.id, paused]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!group || !story) return null;

  const sendReply = async (event) => {
    event.preventDefault();
    const text = reply.trim();
    if (!text) return;
    try {
      const conversation = await createConversation([group.authorId]);
      await sendConversationMessage(conversation.id, `Replied to your story: ${text}`, currentUser.id);
      setReply('');
      setPaused(false);
      showToast(`Reply sent to ${group.name}`);
    } catch (error) { showToast(`Reply: ${error.message}`); }
  };
  const removeStory = async () => {
    try {
      await deleteStory(story.id);
      showToast('Story deleted');
      onChanged?.({ reload: true });
      onClose();
    } catch (error) { showToast(`Delete: ${error.message}`); }
  };
  const menu = () => {
    setPaused(true);
    openSheet(group.isOwn
      ? [{ label: 'Delete story', danger: true, onClick: removeStory }, { label: 'Add another story', onClick: () => { onClose(); openCreate('story'); } }]
      : [
        { label: 'Report', danger: true, onClick: () => openReport({ type: 'story', id: story.id, name: group.name }) },
        { label: `Mute ${group.name}'s stories`, onClick: async () => { await setUserMuted(group.name, { stories: true }).catch(() => {}); showToast(`${group.name}'s stories are muted`); onChanged?.({ reload: true }); onClose(); } },
        { label: 'View profile', onClick: () => { onClose(); openProfile(group.name); } },
      ]);
  };

  return <div className="modal-backdrop story-backdrop" onClick={onClose}><div className="story-viewer" onClick={(event) => event.stopPropagation()}>
    <div className="story-progress">{group.stories.map((item, index) => <span key={item.id} className={index < storyIndex ? 'viewed' : ''}>
      {index === storyIndex && <i key={`${item.id}-${paused}`} className={`story-progress-fill ${paused ? 'paused' : ''}`} style={{ animationDuration: `${story.mediaType === 'video' ? 0 : IMAGE_SECONDS}s` }}/>}
    </span>)}</div>
    <header className="story-viewer-header">
      <button className="story-author" onClick={() => { onClose(); openProfile(group.name); }}><img src={group.avatar} alt=""/><b>{group.isOwn ? 'Your story' : group.name}</b><span>{story.time}</span></button>
      <div><button onClick={menu} aria-label="Story options"><MoreHorizontal/></button><button onClick={onClose} aria-label="Close story"><X/></button></div>
    </header>
    {story.mediaType === 'video'
      ? <video key={story.id} className="story-image" src={story.media} autoPlay playsInline onEnded={() => move(1)}/>
      : <img key={story.id} className="story-image" src={story.media} alt={story.caption || `Story by ${group.name}`}/>}
    {story.caption && <p className="story-caption">{story.caption}</p>}
    <button className="story-nav previous" onClick={() => move(-1)} aria-label="Previous story"><ChevronLeft/></button>
    <button className="story-nav next" onClick={() => move(1)} aria-label="Next story"><ChevronRight/></button>
    {group.isOwn
      ? <div className="story-own-footer">
        <button onClick={() => { setPaused(true); setShowViewers(true); }}><Eye/>{viewers === null ? 'Seen by …' : `Seen by ${viewers.length}`}</button>
        <button onClick={removeStory} aria-label="Delete story"><Trash2/></button>
      </div>
      : <form className="story-reply" onSubmit={sendReply}>
        <input value={reply} onFocus={() => setPaused(true)} onBlur={() => !reply && setPaused(false)} onChange={(event) => setReply(event.target.value)} placeholder={`Reply to ${group.name}…`} aria-label="Reply to story"/>
        <button type="submit" disabled={!reply.trim()} aria-label="Send story reply"><Send/></button>
      </form>}
    {showViewers && <div className="story-viewers" onClick={(event) => event.stopPropagation()}>
      <header><b>Seen by {viewers?.length || 0}</b><button onClick={() => { setShowViewers(false); setPaused(false); }} aria-label="Close viewers"><X/></button></header>
      {(viewers || []).map((viewer) => <button key={viewer.id} onClick={() => { onClose(); openProfile(viewer.name); }}><img src={viewer.avatar} alt=""/><b>{viewer.name}</b><small>{viewer.time}</small></button>)}
      {viewers?.length === 0 && <p>No views yet.</p>}
    </div>}
  </div></div>;
}
