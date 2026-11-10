import React from 'react';
import { Bookmark, Heart, MessageCircle, MoreHorizontal, Send } from 'lucide-react';
import { formatCount } from '../api';
import { useApp } from '../context';
import { Caption, MediaView } from './Media';
import { usePostEngagement, usePostMenu } from './postActions';
import { FollowButton } from './Sheets';

export function PostCard({ post, onHidden, onDeleted, onCommentAdded }) {
  const { openProfile, openPost, openShare, navigate } = useApp();
  const { liked, likeCount, saved, toggleLike, toggleSave } = usePostEngagement(post);
  const openMenu = usePostMenu();
  const showFollow = post.followStatus === 'none' || post.followStatus === 'requested';
  return <article className="post">
    {post.isSuggested && <div className="post-suggested-label">Suggested for you</div>}
    <header className="post-header">
      <button className="avatar-button" onClick={() => openProfile(post.name)}><img className="avatar" src={post.avatar} alt=""/></button>
      <div className="post-author">
        <b role="button" tabIndex={0} onClick={() => openProfile(post.name)}>{post.name}</b>
        {post.place && <span role="button" tabIndex={0} onClick={() => navigate('Explore', { topic: post.place })}>{post.place}</span>}
      </div>
      {showFollow && <FollowButton name={post.name} initialStatus={post.followStatus} className="follow-inline"/>}
      <button className="icon-button" onClick={() => openMenu(post, { onHidden, onDeleted })} aria-label="Post options"><MoreHorizontal/></button>
    </header>
    <MediaView post={post} onDoubleTap={() => toggleLike(true)}/>
    <div className="post-actions">
      <div>
        <button onClick={() => toggleLike()} className={liked ? 'liked' : ''} aria-label={liked ? 'Unlike' : 'Like'}><Heart fill={liked ? 'currentColor' : 'none'}/></button>
        <button onClick={() => openPost(post, { onCommentAdded })} aria-label="Comment"><MessageCircle/></button>
        <button onClick={() => openShare(post)} aria-label="Share"><Send/></button>
      </div>
      <button onClick={toggleSave} className={saved ? 'saved' : ''} aria-label={saved ? 'Remove from saved' : 'Save'}><Bookmark fill={saved ? 'currentColor' : 'none'}/></button>
    </div>
    <div className="post-copy">
      <b>{formatCount(likeCount)} {likeCount === 1 ? 'like' : 'likes'}</b>
      {post.caption && <p><b role="button" tabIndex={0} onClick={() => openProfile(post.name)}>{post.name}</b> <Caption text={post.caption} onHashtag={(tag) => navigate('Explore', { topic: `#${tag}` })}/></p>}
      {post.commentCount > 0
        ? <button className="muted" onClick={() => openPost(post, { onCommentAdded })}>View {post.commentCount === 1 ? '1 comment' : `all ${post.commentCount} comments`}</button>
        : <button className="muted" onClick={() => openPost(post, { onCommentAdded })}>Add a comment…</button>}
      <span className="timestamp">{post.time}</span>
    </div>
  </article>;
}
