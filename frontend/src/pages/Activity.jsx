import React, { useEffect, useState } from 'react';
import { acceptFollowRequest, declineFollowRequest, fetchNotifications, markAllNotificationsRead, markNotificationRead } from '../api';
import { useApp } from '../context';
import { ListSkeleton } from '../components/Skeleton';

const FILTERS = [['all', 'All'], ['follows', 'Follows'], ['requests', 'Requests']];

function bucket(createdAt, unread) {
  if (unread) return 'New';
  const days = (Date.now() - new Date(createdAt).getTime()) / 86400000;
  if (days < 1) return 'Today';
  if (days < 7) return 'This week';
  return 'Earlier';
}

export function ActivityPage() {
  const { openProfile, openPost, refreshUnread, showToast } = useApp();
  const [items, setItems] = useState(null);
  const [filter, setFilter] = useState('all');
  useEffect(() => { fetchNotifications().then(setItems).catch((error) => { showToast(error.message); setItems([]); }); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const markRead = (item) => {
    if (!item.unread) return;
    setItems((current) => current.map((row) => (row.id === item.id ? { ...row, unread: false } : row)));
    markNotificationRead(item.id).then(refreshUnread).catch(() => {});
  };
  const open = (item) => {
    markRead(item);
    if (item.type === 'request') return;
    if (item.postId) openPost(item.postId); else openProfile(item.name);
  };
  const respond = async (item, accept) => {
    try {
      await (accept ? acceptFollowRequest(item.name) : declineFollowRequest(item.name));
      setItems((current) => (accept
        ? current.map((row) => (row.id === item.id ? { ...row, type: 'follow', text: 'started following you.', unread: false } : row))
        : current.filter((row) => row.id !== item.id)));
      refreshUnread();
      showToast(accept ? `${item.name} can now see your posts` : 'Request deleted');
    } catch (error) { showToast(`Request: ${error.message}`); }
  };
  const markAll = async () => {
    try { await markAllNotificationsRead(); setItems((current) => current.map((row) => ({ ...row, unread: false }))); refreshUnread(); } catch (error) { showToast(error.message); }
  };

  const filtered = (items || []).filter((item) => filter === 'all'
    || (filter === 'requests' && item.type === 'request')
    || (filter === 'follows' && ['follow', 'follow_accept'].includes(item.type)));
  const groups = filtered.reduce((acc, item) => {
    const key = bucket(item.createdAt, item.unread);
    (acc[key] = acc[key] || []).push(item);
    return acc;
  }, {});
  const requestCount = (items || []).filter((item) => item.type === 'request').length;

  return <section className="activity-page">
    <header className="activity-header"><h1>Activity</h1>{items?.some((item) => item.unread) && <button onClick={markAll}>Mark all as read</button>}</header>
    <div className="activity-filters">{FILTERS.map(([key, label]) => <button key={key} className={filter === key ? 'active-activity-filter' : ''} onClick={() => setFilter(key)}>{label}{key === 'requests' && requestCount > 0 ? ` (${requestCount})` : ''}</button>)}</div>
    <section className="activity-list">
      {items === null && <ListSkeleton rows={6}/>}
      {items !== null && !filtered.length && <div className="empty-state compact"><b>{filter === 'requests' ? 'No follow requests' : 'No activity yet'}</b><p>When people like, comment on or save your posts, or follow you, you'll see it here.</p></div>}
      {['New', 'Today', 'This week', 'Earlier'].filter((key) => groups[key]).map((key) => <React.Fragment key={key}>
        <h2>{key}</h2>
        {groups[key].map((item) => <div className={`activity-row ${item.unread ? 'unread' : ''}`} key={item.id} role="button" tabIndex={0} onClick={() => open(item)}>
          <img src={item.avatar} alt="" onClick={(event) => { event.stopPropagation(); markRead(item); openProfile(item.name); }}/>
          <span><b>{item.name}</b> {item.text}<small>{item.time}</small></span>
          {item.type === 'request'
            ? <span className="activity-actions">
              <button className="activity-confirm" onClick={(event) => { event.stopPropagation(); respond(item, true); }}>Confirm</button>
              <button className="activity-following" onClick={(event) => { event.stopPropagation(); respond(item, false); }}>Delete</button>
            </span>
            : item.image && <img className="activity-thumbnail" src={item.image} alt=""/>}
        </div>)}
      </React.Fragment>)}
    </section>
  </section>;
}
