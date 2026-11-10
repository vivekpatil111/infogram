import React, { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ImagePlus, MoreHorizontal, PenSquare, Search, Send } from 'lucide-react';
import {
  createConversation, fetchConversations, fetchMessages, markConversationRead, normalizeMessage,
  fetchPost, openConversationSocket, sendConversationMessage, setUserBlocked, uploadMedia,
} from '../api';
import { EmojiButton, insertAtCaret } from '../components/Emoji';
import { useApp } from '../context';
import { NewMessageModal } from '../components/Sheets';
import { ListSkeleton, Spinner } from '../components/Skeleton';

const POST_LINK = /https?:\/\/[^\s]+\/post\/(\d+)/;
const IMAGE_URL = /^https?:\/\/\S+\.(jpe?g|png|webp)(\?\S*)?$/i;
const VIDEO_URL = /^https?:\/\/\S+\.(mp4|webm)(\?\S*)?$/i;

function MessageBody({ text, onOpenPost }) {
  const trimmed = text.trim();
  if (IMAGE_URL.test(trimmed)) return <img className="message-media" src={trimmed} alt="Shared photo"/>;
  if (VIDEO_URL.test(trimmed)) return <video className="message-media" src={trimmed} controls playsInline preload="metadata"/>;
  const post = text.match(POST_LINK);
  if (post) return <SharedPostCard postId={Number(post[1])} onOpenPost={onOpenPost}/>;
  return text;
}

// A post shared in a chat shows as a tappable preview, not a bare link.
const sharedPostCache = new Map();
function SharedPostCard({ postId, onOpenPost }) {
  const [post, setPost] = useState(sharedPostCache.get(postId) || null);
  const [missing, setMissing] = useState(false);
  useEffect(() => {
    if (post) return;
    let cancelled = false;
    fetchPost(postId)
      .then((data) => { sharedPostCache.set(postId, data); if (!cancelled) setPost(data); })
      .catch(() => { if (!cancelled) setMissing(true); });
    return () => { cancelled = true; };
  }, [postId]); // eslint-disable-line react-hooks/exhaustive-deps
  if (missing) return <span className="shared-post missing">Post unavailable</span>;
  return <button className="shared-post" onClick={() => onOpenPost(postId)}>
    {post ? <>
      <span className="shared-post-head"><img src={post.avatar} alt=""/><b>{post.name}</b></span>
      {post.mediaType === 'video' && !post.poster ? <video src={post.image} muted preload="metadata"/> : <img className="shared-post-media" src={post.poster || post.image} alt=""/>}
      {post.caption && <small>{post.caption.slice(0, 90)}</small>}
    </> : <span className="sk shared-post-skeleton"/>}
  </button>;
}

export function MessagesPage({ target, onTargetHandled, unreadMessages }) {
  const { currentUser, openProfile, openPost, openSheet, openReport, refreshUnread, showToast } = useApp();
  const [conversations, setConversations] = useState(null);
  const [activeId, setActiveId] = useState(null);
  const [mobileChatOpen, setMobileChatOpen] = useState(false);
  const [composer, setComposer] = useState('');
  const [sending, setSending] = useState(false);
  const [search, setSearch] = useState('');
  const [newMessageOpen, setNewMessageOpen] = useState(false);
  const bottomRef = useRef(null);
  const fileRef = useRef(null);
  const composerRef = useRef(null);

  const loadList = () => fetchConversations(currentUser.id)
    .then((rows) => setConversations((current) => rows.map((row) => {
      const existing = current?.find((item) => item.id === row.id);
      return existing?.loaded ? { ...row, messages: existing.messages, loaded: true, unreadCount: row.id === activeId ? 0 : row.unreadCount } : row;
    })))
    .catch((error) => { showToast(`Messages: ${error.message}`); setConversations((current) => current || []); });
  useEffect(() => { loadList(); }, [unreadMessages]); // eslint-disable-line react-hooks/exhaustive-deps

  // "Message" from a profile: open (or create) the 1:1 thread.
  useEffect(() => {
    if (!target) return;
    createConversation([target.id])
      .then(async (conversation) => { await loadList(); setActiveId(conversation.id); setMobileChatOpen(true); })
      .catch((error) => showToast(`Message: ${error.message}`))
      .finally(onTargetHandled);
  }, [target]); // eslint-disable-line react-hooks/exhaustive-deps

  // Open chat: history, mark read, live updates.
  useEffect(() => {
    if (!activeId) return undefined;
    let socket = null;
    let closed = false;
    const patch = (fn) => setConversations((current) => (current || []).map((item) => (item.id === activeId ? fn(item) : item)));
    fetchMessages(activeId, currentUser.id).then((messages) => {
      if (closed) return;
      patch((item) => ({ ...item, messages, loaded: true, unreadCount: 0 }));
      markConversationRead(activeId).then(refreshUnread).catch(() => {});
    }).catch((error) => showToast(`Messages: ${error.message}`));
    openConversationSocket(activeId, (raw) => {
      const message = normalizeMessage(raw, currentUser.id);
      patch((item) => (item.messages.some((existing) => existing.id === message.id) ? item : { ...item, preview: message.text, time: message.time, messages: [...item.messages, message] }));
      if (raw.sender?.id !== currentUser.id) markConversationRead(activeId).catch(() => {});
    }).then((ws) => { if (closed) ws.close(); else socket = ws; }).catch(() => {});
    return () => { closed = true; socket?.close(); };
  }, [activeId]); // eslint-disable-line react-hooks/exhaustive-deps

  const active = conversations?.find((item) => item.id === activeId);
  useEffect(() => { bottomRef.current?.scrollIntoView({ block: 'end' }); }, [active?.messages.length]);

  const deliver = async (body) => {
    const message = await sendConversationMessage(activeId, body, currentUser.id);
    setConversations((current) => current.map((item) => (item.id !== activeId || item.messages.some((existing) => existing.id === message.id)
      ? item : { ...item, preview: `You: ${message.text}`, time: 'now', messages: [...item.messages, message] })));
  };
  const send = async (event) => {
    event.preventDefault();
    const body = composer.trim();
    if (!body || sending) return;
    setSending(true);
    try { await deliver(body); setComposer(''); } catch (error) { showToast(`Message: ${error.message}`); } finally { setSending(false); }
  };
  const sendMedia = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setSending(true);
    try { await deliver((await uploadMedia(file)).media_url); } catch (error) { showToast(`Media: ${error.message}`); } finally { setSending(false); }
  };
  const chatMenu = () => openSheet([
    { label: 'View profile', onClick: () => openProfile(active.name) },
    { label: 'Report', danger: true, onClick: () => openReport({ type: 'user', id: active.name, name: active.name }) },
    { label: 'Block', danger: true, onClick: async () => {
      try { await setUserBlocked(active.name, true); showToast(`${active.name} is blocked. They can't message you.`); } catch (error) { showToast(error.message); }
    } },
  ]);
  const startNew = async (person) => {
    setNewMessageOpen(false);
    try {
      const conversation = await createConversation([person.id]);
      await loadList();
      setActiveId(conversation.id);
      setMobileChatOpen(true);
    } catch (error) { showToast(`New message: ${error.message}`); }
  };

  const visible = (conversations || []).filter((item) => item.name.toLowerCase().includes(search.toLowerCase()));
  const isGroup = active?.name.includes(', ');
  return <section className="messages-page"><div className={`messages-layout ${mobileChatOpen ? 'mobile-chat-open' : ''}`}>
    <aside className="inbox-panel">
      <header><h1>Messages</h1><button aria-label="New message" onClick={() => setNewMessageOpen(true)}><PenSquare/></button></header>
      <div className="message-search"><Search/><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search messages"/></div>
      <div className="conversation-list">
        {conversations === null && <ListSkeleton rows={6}/>}
        {conversations?.length === 0 && <div className="empty-state compact"><b>No messages yet</b><p>Start a conversation with someone you follow.</p><button onClick={() => setNewMessageOpen(true)}>Send message</button></div>}
        {visible.map((conversation) => <button key={conversation.id} className={`conversation ${conversation.id === activeId ? 'active-conversation' : ''} ${conversation.unreadCount ? 'unread' : ''}`}
          onClick={() => { setActiveId(conversation.id); setMobileChatOpen(true); }}>
          <span className="conversation-avatar"><img src={conversation.avatar} alt=""/></span>
          <span className="conversation-copy"><b>{conversation.name}</b><small>{IMAGE_URL.test(conversation.preview.replace('You: ', '')) ? 'Sent a photo' : conversation.preview}</small></span>
          <time>{conversation.time}</time>{conversation.unreadCount > 0 && <i className="unread-dot" aria-label="Unread"/>}
        </button>)}
      </div>
    </aside>
    <section className="chat-panel">
      {!active && <div className="empty-state chat-empty"><b>Your messages</b><p>Send private photos and messages to a friend.</p><button onClick={() => setNewMessageOpen(true)}>Send message</button></div>}
      {active && <>
        <header className="chat-header">
          <button className="chat-back" onClick={() => setMobileChatOpen(false)} aria-label="Back to messages"><ChevronLeft/></button>
          <button className="chat-person" onClick={() => !isGroup && openProfile(active.name)}><span className="conversation-avatar"><img src={active.avatar} alt=""/></span><span><b>{active.name}</b><small>{isGroup ? 'Group' : 'View profile'}</small></span></button>
          {!isGroup && <div><button aria-label="Conversation options" onClick={chatMenu}><MoreHorizontal/></button></div>}
        </header>
        <div className="chat-messages">
          {!active.loaded && <div className="center-spinner"><Spinner/></div>}
          {active.loaded && !active.messages.length && <p className="new-message-status">Say hi to {active.name} 👋</p>}
          {active.messages.map((message, index) => <div className={`message-row ${message.from === 'me' ? 'mine' : ''}`} key={message.id || index}>
            <p><MessageBody text={message.text} onOpenPost={(id) => openPost(id)}/><small>{message.time}</small></p>
          </div>)}
          <div ref={bottomRef}/>
        </div>
        <form className="message-composer" onSubmit={send}>
          <button type="button" aria-label="Send a photo or video" onClick={() => fileRef.current?.click()} disabled={sending}><ImagePlus/></button>
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm" hidden onChange={sendMedia}/>
          <EmojiButton onPick={(emoji) => insertAtCaret(composerRef.current, composer, emoji, setComposer)}/>
          <input ref={composerRef} value={composer} onChange={(event) => setComposer(event.target.value)} placeholder={sending ? 'Sending…' : 'Message…'} maxLength="5000"/>
          <button className="send-message" disabled={!composer.trim() || sending} aria-label="Send message"><Send/></button>
        </form>
      </>}
    </section>
    {newMessageOpen && <NewMessageModal onClose={() => setNewMessageOpen(false)} onSelect={startNew}/>}
  </div></section>;
}
