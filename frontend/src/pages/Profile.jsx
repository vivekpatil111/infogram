import React, { useEffect, useRef, useState } from 'react';
import { Bookmark, Camera, Clapperboard, Grid3x3, Heart, Layers, MessageCircle, MoreHorizontal, X } from 'lucide-react';
import { avatarOf, changePassword, fetchBlockedAccounts, fetchFollowList, fetchProfile, formatCount, setUserBlocked, setUserMuted, updateProfile, uploadMedia } from '../api';
import { useApp } from '../context';
import { FollowButton, PeopleModal } from '../components/Sheets';

const TABS = [['posts', 'Posts', Grid3x3], ['reels', 'Reels', Clapperboard], ['saved', 'Saved', Bookmark]];

export function ProfilePage({ username, initialTab, startEditing = false }) {
  const { currentUser, setCurrentUser, openPost, openSheet, openReport, openChat, openAbout, followStatusOf, showToast } = useApp();
  const isOwn = username === currentUser?.username;
  const [tab, setTab] = useState(initialTab === 'saved' && !isOwn ? 'posts' : initialTab || 'posts');
  const [profile, setProfile] = useState(null);
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');
  const [peopleList, setPeopleList] = useState(null);
  const [editing, setEditing] = useState(Boolean(startEditing && isOwn));
  const isMe = isOwn;

  const load = () => {
    setItems(null);
    fetchProfile(username, tab)
      .then((data) => { setProfile(data.profile); setItems(data.items); setError(''); })
      .catch((requestError) => { setError(requestError.status === 404 ? "Sorry, this page isn't available." : requestError.message); setItems([]); });
  };
  useEffect(load, [username, tab]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error && !profile) return <section className="profile-page"><div className="empty-state"><b>{error}</b><p>The link may be broken, or the account may have been removed.</p></div></section>;
  if (!profile) return <section className="profile-page"><div className="profile-header skeleton-header"/></section>;

  const followStatus = followStatusOf(profile.username, profile.follow_status);
  const toggleBlock = async () => {
    try {
      await setUserBlocked(profile.username, !profile.is_blocked);
      showToast(profile.is_blocked ? `${profile.username} is unblocked` : `${profile.username} is blocked. They can't find your profile, posts or stories.`);
      load();
    } catch (requestError) { showToast(`Block: ${requestError.message}`); }
  };
  const toggleMute = async (part) => {
    const next = !profile[`${part}_muted`];
    try {
      await setUserMuted(profile.username, { [part]: next });
      setProfile((current) => ({ ...current, [`${part}_muted`]: next }));
      showToast(next ? `${profile.username}'s ${part} are muted. They won't be told.` : `${profile.username}'s ${part} are unmuted`);
    } catch (requestError) { showToast(`Mute: ${requestError.message}`); }
  };
  const menu = () => openSheet([
    { label: profile.is_blocked ? 'Unblock' : 'Block', danger: !profile.is_blocked, onClick: toggleBlock },
    { label: 'Report', danger: true, hidden: profile.is_blocked, onClick: () => openReport({ type: 'user', id: profile.username, name: profile.username }) },
    { label: profile.posts_muted ? 'Unmute posts' : 'Mute posts', hidden: profile.is_blocked, onClick: () => toggleMute('posts') },
    { label: profile.stories_muted ? 'Unmute stories' : 'Mute stories', hidden: profile.is_blocked, onClick: () => toggleMute('stories') },
    { label: 'About this account', onClick: () => openAbout(profile.username) },
    { label: 'Copy profile link', onClick: () => { navigator.clipboard?.writeText(`${window.location.origin}/u/${profile.username}`); showToast('Link copied'); } },
  ]);
  const openList = (kind) => {
    if (!profile.can_view_content) { showToast('This account is private'); return; }
    setPeopleList({ title: kind === 'followers' ? 'Followers' : 'Following', load: () => fetchFollowList(profile.username, kind) });
  };
  const drop = (post) => setItems((current) => current.filter((item) => item.id !== post.id));
  const tabs = TABS.filter(([key]) => key !== 'saved' || isMe);

  return <section className="profile-page">
    <header className="profile-header">
      <img className="profile-avatar" src={isMe ? currentUser.avatar : avatarOf(profile)} alt=""/>
      <div className="profile-details">
        <div className="profile-title">
          <h1>{profile.username}</h1>
          {isMe && <button onClick={() => setEditing(true)}>Edit profile</button>}
          {!isMe && (profile.is_blocked
            ? <button onClick={toggleBlock}>Unblock</button>
            : <><FollowButton name={profile.username} initialStatus={profile.follow_status} className="profile-follow" avatar={avatarOf(profile)}
              followingActions={[
                { label: profile.posts_muted ? 'Unmute posts' : 'Mute posts', onClick: () => toggleMute('posts') },
                { label: profile.stories_muted ? 'Unmute stories' : 'Mute stories', onClick: () => toggleMute('stories') },
              ]}/><button onClick={() => openChat({ id: profile.id, name: profile.username })}>Message</button></>)}
          {!isMe && <button className="profile-settings" onClick={menu} aria-label="Account options"><MoreHorizontal/></button>}
        </div>
        <div className="profile-stats">
          <span><b>{formatCount(profile.posts_count)}</b> posts</span>
          <button onClick={() => openList('followers')}><b>{formatCount(profile.followers_count)}</b> followers</button>
          <button onClick={() => openList('following')}><b>{formatCount(profile.following_count)}</b> following</button>
        </div>
        <p><b>{profile.username}</b>{profile.is_private && <span className="private-badge">Private</span>}{profile.follows_me && !isMe && <span className="private-badge">Follows you</span>}<br/>{profile.bio || (isMe ? <span className="muted-text">Add a bio so people know what you teach.</span> : null)}</p>
      </div>
    </header>
    {profile.top_topics?.length > 0 && <div className="profile-topics">{profile.top_topics.map((topic) => <span key={topic}>{topic}</span>)}</div>}
    {profile.is_blocked
      ? <div className="private-profile-notice"><b>You blocked {profile.username}</b><p>They can't see your profile, posts or stories, or message you.</p></div>
      : !profile.can_view_content
        ? <div className="private-profile-notice"><b>This account is private</b><p>{followStatus === 'requested' ? 'Your follow request is pending.' : 'Follow this account to see their posts and reels.'}</p></div>
        : <>
          <nav className="profile-tabs">{tabs.map(([key, label, Icon]) => <button className={tab === key ? 'active-profile-tab' : ''} key={key} onClick={() => setTab(key)}><Icon/>{label}</button>)}</nav>
          {items === null && <div className="profile-grid">{Array.from({ length: 6 }, (_, i) => <div key={i} className="profile-tile skeleton"/>)}</div>}
          {items?.length === 0 && <div className="empty-state"><b>{tab === 'saved' ? 'Nothing saved yet' : tab === 'reels' ? 'No reels yet' : 'No posts yet'}</b><p>{tab === 'saved' ? 'Tap the bookmark on any post to keep it here. Only you can see this.' : isMe ? 'Share something useful you know.' : ''}</p></div>}
          <div className="profile-grid">{(items || []).map((post) => <button className="profile-tile" key={post.id} onClick={() => openPost(post, { onDeleted: drop })}>
            {post.mediaType === 'video' && !post.poster ? <video src={post.image} muted preload="metadata"/> : <img src={post.poster || post.image} alt={post.caption.slice(0, 80)} loading="lazy"/>}
            {post.mediaType === 'video' && <Clapperboard className="profile-tile-badge"/>}
            {post.mediaType === 'carousel' && <Layers className="profile-tile-badge"/>}
            <span className="tile-stats"><span><Heart fill="currentColor"/>{formatCount(post.likeCount)}</span><span><MessageCircle fill="currentColor"/>{formatCount(post.commentCount)}</span></span>
          </button>)}</div>
        </>}
    {peopleList && <PeopleModal title={peopleList.title} load={peopleList.load} onClose={() => setPeopleList(null)}/>}
    {editing && <ProfileEditModal onClose={() => setEditing(false)} onSaved={(user) => { setCurrentUser(user); setProfile((current) => ({ ...current, ...user })); }}/>}
  </section>;
}

function ProfileEditModal({ onClose, onSaved }) {
  const { currentUser, showToast } = useApp();
  const [bio, setBio] = useState(currentUser.bio || '');
  const [avatarUrl, setAvatarUrl] = useState(currentUser.avatar_url || '');
  const [isPrivate, setIsPrivate] = useState(Boolean(currentUser.is_private));
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [passwords, setPasswords] = useState(null);
  const [blocked, setBlocked] = useState(false);
  const fileRef = useRef(null);

  const choosePhoto = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { setError('Use a JPEG, PNG or WebP image.'); return; }
    setBusy('Uploading photo…');
    setError('');
    try { setAvatarUrl((await uploadMedia(file)).media_url); } catch (requestError) { setError(requestError.message); } finally { setBusy(''); }
  };
  const save = async (event) => {
    event.preventDefault();
    if (busy) return;
    setBusy('Saving…');
    setError('');
    try {
      if (passwords?.next) {
        if (passwords.next !== passwords.confirm) throw new Error("New passwords don't match.");
        await changePassword(passwords.current, passwords.next);
      }
      const updated = await updateProfile({ bio, avatar_url: avatarUrl, is_private: isPrivate });
      onSaved(updated);
      showToast(passwords?.next ? 'Profile and password updated' : 'Profile updated');
      onClose();
    } catch (requestError) { setError(requestError.message); } finally { setBusy(''); }
  };
  const preview = avatarUrl || avatarOf({ username: currentUser.username });

  return <div className="modal-backdrop create-backdrop" onClick={onClose}><section className="create-sheet profile-edit-sheet" onClick={(event) => event.stopPropagation()}>
    <header><b>Edit profile</b><button onClick={onClose} aria-label="Close profile editor"><X/></button></header>
    <form className="create-form profile-edit-form" onSubmit={save}>
      <div className="avatar-editor">
        <img src={preview} alt=""/>
        <div><b>{currentUser.username}</b>
          <button type="button" onClick={() => fileRef.current?.click()}><Camera/>Change photo</button>
          {avatarUrl && <button type="button" className="danger" onClick={() => setAvatarUrl('')}>Remove photo</button>}
        </div>
        <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={choosePhoto}/>
      </div>
      <label>Bio<textarea value={bio} onChange={(event) => setBio(event.target.value)} rows="3" maxLength="500" placeholder="What do you teach or share?"/></label>
      <label className="private-toggle"><input type="checkbox" checked={isPrivate} onChange={(event) => setIsPrivate(event.target.checked)}/><span><b>Private account</b><small>{isPrivate ? 'Only followers you approve can see your posts, reels and stories.' : 'Anyone can see your posts. Switching to public approves pending requests.'}</small></span></label>
      {passwords === null
        ? <button type="button" className="text-button" onClick={() => setPasswords({ current: '', next: '', confirm: '' })}>Change password</button>
        : <fieldset className="password-fields"><legend>Change password</legend>
          <input type="password" autoComplete="current-password" placeholder="Current password" value={passwords.current} onChange={(event) => setPasswords({ ...passwords, current: event.target.value })}/>
          <input type="password" autoComplete="new-password" placeholder="New password" minLength="8" value={passwords.next} onChange={(event) => setPasswords({ ...passwords, next: event.target.value })}/>
          <input type="password" autoComplete="new-password" placeholder="Confirm new password" minLength="8" value={passwords.confirm} onChange={(event) => setPasswords({ ...passwords, confirm: event.target.value })}/>
          <small>Changing it signs you out on other devices.</small>
        </fieldset>}
      <button type="button" className="text-button" onClick={() => setBlocked(true)}>Blocked accounts</button>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <div className="create-footer"><span>{busy || 'Keep your profile informative'}</span><button disabled={Boolean(busy)}>{busy ? 'Please wait…' : 'Save'}</button></div>
    </form>
    {blocked && <BlockedModal onClose={() => setBlocked(false)}/>}
  </section></div>;
}

function BlockedModal({ onClose }) {
  const { showToast } = useApp();
  return <PeopleModal title="Blocked accounts" load={fetchBlockedAccounts} emptyText="You haven't blocked anyone." onClose={onClose}
    renderAction={(person, { remove }) => <button className="person-follow" onClick={async () => {
      try { await setUserBlocked(person.name, false); remove(person.name); showToast(`${person.name} is unblocked`); } catch (error) { showToast(error.message); }
    }}>Unblock</button>}/>;
}
