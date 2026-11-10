import React, { useRef, useState } from 'react';
import { Bookmark, Heart, MessageCircle, MoreHorizontal, Send } from 'lucide-react';
import { addPostComment, formatCount } from '../api';
import { useApp } from '../context';
import { Caption, MediaView } from './Media';
import { usePostEngagement, usePostMenu } from './postActions';
import { FollowButton } from './Sheets';
import { EmojiButton, insertAtCaret } from './Emoji';
import { PathChip, ResourceButton, VerifiedBadge, VerticalPill, useSeen } from './Knowledge';

const CAPTION_PREVIEW = 125;

export function PostCard({ post, onHidden, onDeleted, onCommentAdded }) {
  const { currentUser, openProfile, openPost, openShare, openLikes, navigate, showToast } = useApp();
  const { liked, likeCount, saved, toggleLike, toggleSave } = usePostEngagement(post);
  const openMenu = usePostMenu();
  const showFollow = post.followStatus === 'none' || post.followStatus === 'requested';
  const [expanded, setExpanded] = useState(false);
  const [draft, setDraft] = useState('');
  const [posting, setPosting] = useState(false);
  const [myComments, setMyComments] = useState([]);
  const inputRef = useRef(null);
  const cardRef = useRef(null);
  useSeen(cardRef, post.id);
  const longCaption = (post.caption || '').length > CAPTION_PREVIEW || (post.caption || '').split('\n').length > 2;
  const caption = longCaption && !expanded ? `${post.caption.slice(0, CAPTION_PREVIEW).split('\n').slice(0, 2).join('\n').trimEnd()}…` : post.caption;
  const submitComment = async (event) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || posting) return;
    setPosting(true);
    try {
      const comment = await addPostComment(post.id, text);
      setMyComments((current) => [...current, comment]);
      setDraft('');
      onCommentAdded?.(post.id);
    } catch (error) { showToast(`Comment: ${error.message}`); } finally { setPosting(false); }
  };
  return <article className="post" ref={cardRef}>
    {post.isSuggested && <div className="post-suggested-label">Suggested for you</div>}
    <header className="post-header">
      <button className="avatar-button" onClick={() => openProfile(post.name)}><img className="avatar" src={post.avatar} alt=""/></button>
      <div className="post-author">
        <b role="button" tabIndex={0} onClick={() => openProfile(post.name)}>{post.name}<VerifiedBadge verified={post.verified} title={post.expertTitle}/></b>
        {post.location
          ? <span role="button" tabIndex={0} className="post-location" onClick={() => navigate('Location', { slug: post.location.slug })}>{post.location.name}</span>
          : post.place && <span role="button" tabIndex={0} onClick={() => navigate('Explore', { topic: post.place })}>{post.place}</span>}
      </div>
      {showFollow && <FollowButton name={post.name} initialStatus={post.followStatus} className="follow-inline"/>}
      <button className="icon-button" onClick={() => openMenu(post, { onHidden, onDeleted })} aria-label="Post options"><MoreHorizontal/></button>
    </header>
    <MediaView post={post} onDoubleTap={() => toggleLike(true)}/>
    <div className="post-actions">
      <div>
        <button onClick={() => toggleLike()} className={liked ? 'liked' : ''} aria-label={liked ? 'Unlike' : 'Like'}><Heart fill={liked ? 'currentColor' : 'none'}/></button>
        <button onClick={() => inputRef.current?.focus()} aria-label="Comment"><MessageCircle/></button>
        <button onClick={() => openShare(post)} aria-label="Share"><Send/></button>
      </div>
      <div className="post-actions-right">
        <ResourceButton post={post}/>
        <button onClick={toggleSave} className={saved ? 'saved' : ''} aria-label={saved ? 'Remove from saved' : 'Save'}><Bookmark fill={saved ? 'currentColor' : 'none'}/></button>
      </div>
    </div>
    <div className="post-copy">
      {(post.paths.length > 0 || post.vertical) && <div className="post-knowledge"><PathChip paths={post.paths}/>{!post.paths.length && <VerticalPill slug={post.vertical}/>}</div>}
      {likeCount > 0 ? <button className="like-count" onClick={() => openLikes(post.id)}>{formatCount(likeCount)} {likeCount === 1 ? 'like' : 'likes'}</button> : <span className="like-count muted-text">Be the first to like this</span>}
      {post.caption && <p className="post-caption"><b role="button" tabIndex={0} onClick={() => openProfile(post.name)}>{post.name}</b> <Caption text={caption} onHashtag={(tag) => navigate('Explore', { topic: `#${tag}` })}/>
        {longCaption && !expanded && <button className="caption-more" onClick={() => setExpanded(true)}>more</button>}</p>}
      {post.commentCount > 0
        ? <button className="muted" onClick={() => openPost(post, { onCommentAdded })}>View {post.commentCount === 1 ? '1 comment' : `all ${post.commentCount} comments`}</button>
        : null}
      {myComments.map((comment) => <p key={comment.id} className="my-comment"><b>{currentUser?.username}</b> {comment.text}</p>)}
      <span className="timestamp">{post.time}</span>
      <form className="inline-comment" onSubmit={submitComment}>
        <input ref={inputRef} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Add a comment…" aria-label="Add a comment" maxLength="2200"/>
        {draft.trim() && <button className="inline-comment-post" disabled={posting}>{posting ? '…' : 'Post'}</button>}
        <EmojiButton onPick={(emoji) => insertAtCaret(inputRef.current, draft, emoji, setDraft)}/>
      </form>
    </div>
  </article>;
}
