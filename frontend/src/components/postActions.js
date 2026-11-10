import { useState } from 'react';
import { deletePost, postLink, setPostLike, setPostSaved } from '../api';
import { useApp } from '../context';

// Like / save with optimistic counts; rolls back if the request fails.
export function usePostEngagement(post) {
  const { showToast } = useApp();
  const [liked, setLiked] = useState(post.likedByMe);
  const [likeCount, setLikeCount] = useState(post.likeCount);
  const [saved, setSaved] = useState(post.savedByMe);
  const toggleLike = async (force) => {
    const next = typeof force === 'boolean' ? force : !liked;
    if (next === liked) return;
    setLiked(next);
    setLikeCount((count) => count + (next ? 1 : -1));
    try { await setPostLike(post.id, next); } catch (error) {
      setLiked(!next);
      setLikeCount((count) => count + (next ? -1 : 1));
      showToast(`Like: ${error.message}`);
    }
  };
  const toggleSave = async () => {
    const next = !saved;
    setSaved(next);
    try { await setPostSaved(post.id, next); showToast(next ? 'Saved to your collection' : 'Removed from saved'); } catch (error) {
      setSaved(!next);
      showToast(`Save: ${error.message}`);
    }
  };
  return { liked, likeCount, saved, toggleLike, toggleSave };
}

// The "…" menu for a post. onHidden / onDeleted let the list drop the card.
export function usePostMenu() {
  const { currentUser, openSheet, openReport, openPost, openProfile, followUser, followStatusOf, showToast } = useApp();
  return (post, { onHidden, onDeleted, inModal = false } = {}) => {
    const own = post.authorId === currentUser?.id;
    const status = followStatusOf(post.name, post.followStatus);
    openSheet([
      { label: 'Delete', danger: true, hidden: !own, onClick: () => openSheet([
        { label: 'Delete post', danger: true, onClick: async () => {
          try { await deletePost(post.id); showToast('Post deleted'); onDeleted?.(post); } catch (error) { showToast(`Delete: ${error.message}`); }
        } },
      ]) },
      { label: 'Report', danger: true, hidden: own, onClick: () => openReport({ type: 'post', id: post.id, name: post.name }, () => onHidden?.(post)) },
      { label: 'Unfollow', danger: true, hidden: own || status !== 'following', onClick: () => followUser(post.name, false) },
      { label: 'Go to post', hidden: inModal, onClick: () => openPost(post) },
      { label: 'About this account', hidden: own, onClick: () => openProfile(post.name) },
      { label: 'Copy link', onClick: () => { navigator.clipboard?.writeText(postLink(post.id)); showToast('Link copied'); } },
      { label: 'Hide', hidden: own || !onHidden, onClick: () => { onHidden(post); showToast('Post hidden from your feed'); } },
    ]);
  };
}
