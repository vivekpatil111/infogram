import React, { useEffect, useState } from 'react';
import { ChevronRight, Link2, Search, Send, X } from 'lucide-react';
import { REPORT_REASONS, avatarOf, createConversation, fetchFollowList, fetchLikers, fetchProfile, postLink, reportContent, searchContent, sendConversationMessage } from '../api';
import { useApp } from '../context';
import { useDebounced } from '../hooks';
import { ListSkeleton } from './Skeleton';

const stop = (event) => event.stopPropagation();
export const followLabel = (status) => (status === 'requested' ? 'Requested' : status === 'following' ? 'Following' : 'Follow');

// Bottom-sheet menu. actions: [{ label, onClick, danger?, hidden? }]
export function ActionSheet({ actions, title, onClose }) {
  return <div className="modal-backdrop menu-backdrop" onClick={onClose}><section className="post-menu" onClick={stop}>
    {title && <div className="sheet-title">{title}</div>}
    {actions.filter((action) => !action.hidden).map((action) => <button key={action.label} className={action.danger ? 'menu-danger' : ''} onClick={() => { onClose(); action.onClick(); }}>{action.label}</button>)}
    <button onClick={onClose}>Cancel</button>
  </section></div>;
}

// Report a post, comment, story or account: pick a reason, optional details.
export function ReportSheet({ target, onClose, onReported }) {
  const [reason, setReason] = useState(null);
  const [details, setDetails] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const submit = async () => {
    if (!reason || busy) return;
    setBusy(true);
    setError('');
    try {
      await reportContent({ targetType: target.type, targetId: target.id, reason, details });
      onReported?.(target);
      onClose();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };
  const noun = target.type === 'user' ? 'account' : target.type;
  return <div className="modal-backdrop menu-backdrop" onClick={onClose}><section className="report-sheet" onClick={stop}>
    <header><b>Report</b><button onClick={onClose} aria-label="Close report"><X/></button></header>
    {!reason
      ? <><p className="report-question">Why are you reporting this {noun}?</p>
        <div className="report-reasons">{REPORT_REASONS.map(([value, label]) => <button key={value} onClick={() => setReason(value)}>{label}<ChevronRight/></button>)}</div></>
      : <div className="report-confirm">
        <p className="report-question">{REPORT_REASONS.find(([value]) => value === reason)?.[1]}</p>
        <textarea value={details} onChange={(event) => setDetails(event.target.value)} rows="3" maxLength="1000" placeholder="Add details (optional)" />
        <small>Reports are anonymous. The person you report isn't told who reported them.</small>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <div className="report-actions"><button onClick={() => setReason(null)}>Back</button><button className="report-submit" onClick={submit} disabled={busy}>{busy ? 'Sending…' : 'Submit report'}</button></div>
      </div>}
  </section></div>;
}

function PersonRow({ person, action, onOpen }) {
  return <div className="person-row">
    <button className="person-main" onClick={() => onOpen(person.name)}>
      <img src={person.avatar} alt=""/>
      <span><b>{person.name}</b><small>{person.reason || person.bio || `${person.followers} followers`}</small></span>
    </button>
    {action}
  </div>;
}

// Follow button bound to the app-wide follow state.
// Unfollowing / cancelling a request asks first; followingActions adds extra
// rows (mute…) to that sheet, like the "Following" menu on a profile.
export function FollowButton({ name, initialStatus, className = 'person-follow', avatar, followingActions = [] }) {
  const { currentUser, followUser, followStatusOf, openSheet } = useApp();
  const [busy, setBusy] = useState(false);
  if (!name || name === currentUser?.username) return null;
  const status = followStatusOf(name, initialStatus);
  const run = async (follow) => {
    setBusy(true);
    await followUser(name, follow);
    setBusy(false);
  };
  const toggle = () => {
    if (busy) return;
    if (status === 'none') { run(true); return; }
    const requested = status === 'requested';
    openSheet([
      ...(requested ? [] : followingActions),
      { label: requested ? 'Cancel request' : 'Unfollow', danger: true, onClick: () => run(false) },
    ], <>{avatar && <img src={avatar} alt=""/>}<span>{requested ? `Cancel your follow request to ${name}?` : `Unfollow ${name}?`}</span>
      {!requested && <small>If they're private, you'll need to send a new request to see their posts.</small>}</>);
  };
  return <button className={`${className} ${status !== 'none' ? 'is-following' : ''}`} onClick={toggle} disabled={busy}>{followLabel(status)}</button>;
}

// Followers / following / suggestions / blocked lists.
// load() -> person[]; renderAction(person, helpers) overrides the default Follow button.
export function PeopleModal({ title, load, emptyText, renderAction, onClose }) {
  const { openProfile } = useApp();
  const [people, setPeople] = useState(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  useEffect(() => {
    load().then(setPeople).catch((requestError) => { setError(requestError.message); setPeople([]); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const remove = (name) => setPeople((current) => current.filter((person) => person.name !== name));
  const visible = (people || []).filter((person) => person.name.toLowerCase().includes(query.toLowerCase()));
  return <div className="modal-backdrop new-message-backdrop" onClick={onClose}><section className="new-message-sheet" onClick={stop}>
    <header><b>{title}</b><button onClick={onClose} aria-label="Close"><X/></button></header>
    {(people?.length || 0) > 8 && <div className="new-message-search"><Search/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search"/></div>}
    <div className="new-message-results">
      {people === null && <ListSkeleton rows={4}/>}
      {error && <p className="new-message-status">{error}</p>}
      {visible.map((person) => <PersonRow key={person.name} person={person} onOpen={(name) => { onClose(); openProfile(name); }}
        action={renderAction ? renderAction(person, { remove }) : <FollowButton name={person.name} initialStatus={person.followStatus}/>}/>)}
      {people !== null && !error && !visible.length && <p className="new-message-status">{emptyText || 'Nobody here yet.'}</p>}
    </div>
  </section></div>;
}

// Pick someone to start a direct message with.
export function NewMessageModal({ onClose, onSelect }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const term = useDebounced(query.trim());
  useEffect(() => {
    if (term.length < 2) { setResults([]); return undefined; }
    let cancelled = false;
    setBusy(true);
    searchContent(term)
      .then((response) => { if (!cancelled) setResults(response.users); })
      .catch(() => { if (!cancelled) setResults([]); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [term]);
  return <div className="modal-backdrop new-message-backdrop" onClick={onClose}><section className="new-message-sheet" onClick={stop}>
    <header><b>New message</b><button onClick={onClose} aria-label="Close new message dialog"><X/></button></header>
    <div className="new-message-search"><Search/><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search people"/></div>
    <div className="new-message-results">
      {busy && <p className="new-message-status">Searching…</p>}
      {results.map((person) => <button key={person.name} onClick={() => onSelect(person)}><img src={person.avatar} alt=""/><span><b>{person.name}</b><small>{person.bio || `${person.followers} followers`}</small></span><Send/></button>)}
      {!busy && term.length >= 2 && !results.length && <p className="new-message-status">No accounts found.</p>}
      {term.length < 2 && <p className="new-message-status">Type at least 2 letters of a name.</p>}
    </div>
  </section></div>;
}

// Send a post to someone you follow, or copy its link.
export function ShareSheet({ post, onClose }) {
  const { currentUser, showToast } = useApp();
  const [people, setPeople] = useState(null);
  const [query, setQuery] = useState('');
  const [sent, setSent] = useState({});
  const [busy, setBusy] = useState({});
  const term = useDebounced(query.trim());
  useEffect(() => {
    let cancelled = false;
    const loader = term.length >= 2
      ? searchContent(term).then((response) => response.users)
      : fetchFollowList(currentUser.username, 'following');
    loader.then((rows) => { if (!cancelled) setPeople(rows.filter((person) => person.name !== currentUser.username)); }).catch(() => { if (!cancelled) setPeople([]); });
    return () => { cancelled = true; };
  }, [term, currentUser.username]);
  const send = async (person) => {
    if (busy[person.name] || sent[person.name]) return;
    setBusy((current) => ({ ...current, [person.name]: true }));
    try {
      const conversation = await createConversation([person.id]);
      await sendConversationMessage(conversation.id, `Shared an Infogram post: ${postLink(post.id)}`, currentUser.id);
      setSent((current) => ({ ...current, [person.name]: true }));
    } catch (error) {
      showToast(`Share: ${error.message}`);
    } finally {
      setBusy((current) => ({ ...current, [person.name]: false }));
    }
  };
  const copy = () => { navigator.clipboard?.writeText(postLink(post.id)); showToast('Link copied'); onClose(); };
  return <div className="modal-backdrop share-backdrop" onClick={onClose}><section className="share-sheet" onClick={stop}>
    <header><b>Share</b><button onClick={onClose} aria-label="Close share dialog"><X/></button></header>
    <div className="share-search"><Search/><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search people"/></div>
    <div className="share-people">
      {people === null && <ListSkeleton rows={5}/>}
      {(people || []).map((person) => <div className="share-person" key={person.name}>
        <img src={person.avatar} alt=""/><span><b>{person.name}</b><small>{person.bio || 'Send as a message'}</small></span>
        <button className={sent[person.name] ? 'sent' : ''} onClick={() => send(person)} disabled={busy[person.name]}>{busy[person.name] ? 'Sending…' : sent[person.name] ? 'Sent' : 'Send'}</button>
      </div>)}
      {people !== null && !people.length && <p className="no-results">{term.length >= 2 ? 'No accounts found.' : 'Follow people to share posts with them, or search above.'}</p>}
    </div>
    <button className="share-copy" onClick={copy}><Link2/>Copy link</button>
  </section></div>;
}

// "About this account": who this is and how long they've been here.
export function AboutAccountModal({ username, onClose }) {
  const { openProfile } = useApp();
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { fetchProfile(username).then((data) => setProfile(data.profile)).catch((requestError) => setError(requestError.message)); }, [username]);
  const joined = profile?.date_joined ? new Date(profile.date_joined).toLocaleDateString(undefined, { month: 'long', year: 'numeric' }) : '';
  return <div className="modal-backdrop new-message-backdrop" onClick={onClose}><section className="new-message-sheet about-account" onClick={stop}>
    <header><b>About this account</b><button onClick={onClose} aria-label="Close"><X/></button></header>
    {!profile && !error && <ListSkeleton rows={2}/>}
    {error && <p className="new-message-status">{error}</p>}
    {profile && <div className="about-body">
      <img src={avatarOf(profile)} alt=""/>
      <b>{profile.username}</b>
      <p>To help keep our community authentic, we show information about accounts on Infogram.</p>
      <dl>
        <div><dt>Date joined</dt><dd>{joined}</dd></div>
        <div><dt>Account</dt><dd>{profile.is_private ? 'Private' : 'Public'}</dd></div>
        <div><dt>Posts</dt><dd>{profile.posts_count}</dd></div>
      </dl>
      <button onClick={() => { onClose(); openProfile(profile.username); }}>View profile</button>
    </div>}
  </section></div>;
}

// "Liked by" list for a post.
export function LikesModal({ postId, onClose }) {
  return <PeopleModal title="Likes" load={() => fetchLikers(postId)} emptyText="No likes yet." onClose={onClose}/>;
}
