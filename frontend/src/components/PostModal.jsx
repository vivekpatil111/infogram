import React, { useEffect, useRef, useState } from 'react';
import { Bookmark, Heart, MessageCircle, MoreHorizontal, Send, X } from 'lucide-react';
import { addPostComment, deleteComment, fetchComments, fetchPost, formatCount } from '../api';
import { useApp } from '../context';
import { Caption, MediaView } from './Media';
import { usePostEngagement, usePostMenu } from './postActions';
import { FollowButton } from './Sheets';
import { ListSkeleton, Spinner } from './Skeleton';
import { EmojiButton, insertAtCaret } from './Emoji';

// Post detail: media, caption and the full comment thread.
export function PostModal({ postOrId, onClose, onCommentAdded, onDeleted }) {
  const [post, setPost] = useState(typeof postOrId === 'object' ? postOrId : null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (typeof postOrId === 'object') return;
    fetchPost(postOrId).then(setPost).catch((requestError) => setError(requestError.status === 404 ? "This post isn't available. It may have been deleted, or the account is private." : requestError.message));
  }, [postOrId]);
  return <div className="modal-backdrop post-modal-backdrop" onClick={onClose}>
    <button className="post-modal-close" onClick={onClose} aria-label="Close"><X/></button>
    <section className="post-modal" onClick={(event) => event.stopPropagation()}>
      {post ? <PostDetail post={post} onClose={onClose} onCommentAdded={onCommentAdded} onDeleted={onDeleted}/>
        : <p className="post-modal-status">{error || <Spinner/>}</p>}
    </section>
  </div>;
}

function PostDetail({ post, onClose, onCommentAdded, onDeleted }) {
  const { currentUser, openProfile, openShare, openReport, openLikes, navigate, showToast } = useApp();
  const { liked, likeCount, saved, toggleLike, toggleSave } = usePostEngagement(post);
  const openMenu = usePostMenu();
  const [comments, setComments] = useState(null);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);
  useEffect(() => { fetchComments(post.id).then(setComments).catch(() => setComments([])); }, [post.id]);
  const goProfile = (name) => { onClose(); openProfile(name); };
  const submit = async (event) => {
    event.preventDefault();
    const body = text.trim();
    if (!body || busy) return;
    setBusy(true);
    try {
      const comment = await addPostComment(post.id, body);
      setComments((current) => [...(current || []), comment]);
      setText('');
      onCommentAdded?.(post.id);
    } catch (error) { showToast(`Comment: ${error.message}`); } finally { setBusy(false); }
  };
  const remove = async (comment) => {
    try { await deleteComment(post.id, comment.id); setComments((current) => current.filter((item) => item.id !== comment.id)); } catch (error) { showToast(`Delete: ${error.message}`); }
  };
  const reply = (name) => { setText(`@${name} `); inputRef.current?.focus(); };
  const ownPost = post.authorId === currentUser?.id;
  return <>
    <div className="post-modal-media"><MediaView post={post} className="post-modal-image" onDoubleTap={() => toggleLike(true)}/></div>
    <div className="post-modal-side">
      <header className="post-header">
        <button className="avatar-button" onClick={() => goProfile(post.name)}><img className="avatar" src={post.avatar} alt=""/></button>
        <div className="post-author"><b role="button" tabIndex={0} onClick={() => goProfile(post.name)}>{post.name}</b>{post.place && <span>{post.place}</span>}</div>
        <FollowButton name={post.name} initialStatus={post.followStatus} className="follow-inline"/>
        <button className="icon-button" onClick={() => openMenu(post, { inModal: true, onDeleted: (deleted) => { onClose(); onDeleted?.(deleted); } })} aria-label="Post options"><MoreHorizontal/></button>
      </header>
      <div className="post-modal-comments">
        {post.caption && <div className="comment"><img src={post.avatar} alt=""/><p><b>{post.name}</b> <Caption text={post.caption} onHashtag={(tag) => { onClose(); navigate('Explore', { topic: `#${tag}` }); }}/><span>{post.time}</span></p></div>}
        {comments === null && <ListSkeleton rows={3}/>}
        {comments?.map((comment) => <div className="comment" key={comment.id}>
          <button className="avatar-button" onClick={() => goProfile(comment.name)}><img src={comment.avatar} alt=""/></button>
          <p><b role="button" tabIndex={0} onClick={() => goProfile(comment.name)}>{comment.name}</b> {comment.text}
            <span>{comment.time}
              <button className="comment-action" onClick={() => reply(comment.name)}>Reply</button>
              {comment.authorId !== currentUser?.id && <button className="comment-action" onClick={() => openReport({ type: 'comment', id: comment.id, name: comment.name })}>Report</button>}
              {(comment.authorId === currentUser?.id || ownPost) && <button className="comment-action danger" onClick={() => remove(comment)}>Delete</button>}
            </span>
          </p>
        </div>)}
        {comments?.length === 0 && !post.caption && <p className="empty-comments">No comments yet. Start the conversation.</p>}
      </div>
      <div className="post-actions">
        <div>
          <button onClick={() => toggleLike()} className={liked ? 'liked' : ''} aria-label={liked ? 'Unlike' : 'Like'}><Heart fill={liked ? 'currentColor' : 'none'}/></button>
          <button onClick={() => inputRef.current?.focus()} aria-label="Comment"><MessageCircle/></button>
          <button onClick={() => openShare(post)} aria-label="Share"><Send/></button>
        </div>
        <button onClick={toggleSave} className={saved ? 'saved' : ''} aria-label={saved ? 'Remove from saved' : 'Save'}><Bookmark fill={saved ? 'currentColor' : 'none'}/></button>
      </div>
      <div className="post-copy">{likeCount > 0 ? <button className="like-count" onClick={() => openLikes(post.id)}>{formatCount(likeCount)} {likeCount === 1 ? 'like' : 'likes'}</button> : <span className="like-count muted-text">Be the first to like this</span>}<span className="timestamp">{post.time}</span></div>
      <form className="comment-form" onSubmit={submit}>
        <EmojiButton onPick={(emoji) => insertAtCaret(inputRef.current, text, emoji, setText)}/>
        <input ref={inputRef} value={text} onChange={(event) => setText(event.target.value)} placeholder="Add a comment…" aria-label="Add a comment" maxLength="2200"/>
        <button disabled={!text.trim() || busy}>{busy ? '…' : 'Post'}</button>
      </form>
    </div>
  </>;
}
