import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Clapperboard, Compass, Heart, House, Instagram, LogOut, PlusSquare, Search, Send, UserRound } from 'lucide-react';
import { SESSION_EXPIRED_EVENT, avatarOf, fetchCurrentUser, fetchUnreadCounts, hasAccessToken, logout, setUserFollow } from './api';
import { AppContext } from './context';
import { AuthScreen, ResetPasswordScreen } from './components/AuthScreens';
import { CreateSheet } from './components/CreateSheet';
import { PostModal } from './components/PostModal';
import { ActionSheet, ReportSheet, ShareSheet } from './components/Sheets';
import { ActivityPage } from './pages/Activity';
import { ExplorePage } from './pages/Explore';
import { HomePage } from './pages/Home';
import { MessagesPage } from './pages/Messages';
import { ProfilePage } from './pages/Profile';
import { ReelsPage } from './pages/Reels';
import { SearchPanel } from './pages/Search';

// ---- URL <-> page ---------------------------------------------------------
function parseLocation() {
  const { pathname, search } = window.location;
  const params = new URLSearchParams(search);
  const post = pathname.match(/^\/post\/(\d+)\/?$/);
  if (post) return { page: { name: 'Home' }, postId: Number(post[1]) };
  const user = pathname.match(/^\/u\/([^/]+)\/?$/);
  if (user) return { page: { name: 'Profile', username: decodeURIComponent(user[1]) } };
  const simple = { '/explore': 'Explore', '/reels': 'Reels', '/messages': 'Messages', '/activity': 'Activity' }[pathname.replace(/\/$/, '')];
  if (simple) return { page: { name: simple, topic: params.get('topic') || '' } };
  return { page: { name: 'Home' } };
}

function pathFor(page) {
  if (page.name === 'Profile') return `/u/${encodeURIComponent(page.username)}`;
  if (page.name === 'Explore') return page.topic ? `/explore?topic=${encodeURIComponent(page.topic)}` : '/explore';
  return { Reels: '/reels', Messages: '/messages', Activity: '/activity' }[page.name] || '/';
}

function readResetLink() {
  const params = new URLSearchParams(window.location.search);
  return window.location.pathname.startsWith('/reset-password') && params.get('uid') && params.get('token')
    ? { uid: params.get('uid'), token: params.get('token') } : null;
}

const withAvatar = (user) => (user ? { ...user, avatar: avatarOf(user) } : null);

export default function App() {
  const [authenticated, setAuthenticated] = useState(hasAccessToken());
  const [resetLink, setResetLink] = useState(readResetLink);
  const [currentUser, setCurrentUserState] = useState(null);
  const initial = useRef(parseLocation());
  const [page, setPage] = useState(initial.current.page);
  const [postView, setPostView] = useState(initial.current.postId ? { postOrId: initial.current.postId, options: {} } : null);
  const postPushed = useRef(false);
  const [sheet, setSheet] = useState(null);
  const [report, setReport] = useState(null);
  const [share, setShare] = useState(null);
  const [create, setCreate] = useState(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [chatTarget, setChatTarget] = useState(null);
  const [createdPost, setCreatedPost] = useState(null);
  const [storiesVersion, setStoriesVersion] = useState(0);
  const [followOverrides, setFollowOverrides] = useState({});
  const [unread, setUnread] = useState({ notifications: 0, messages: 0 });
  const [toast, setToast] = useState('');
  const toastTimer = useRef(null);

  const showToast = useCallback((message) => {
    setToast(message);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(''), 2600);
  }, []);
  const setCurrentUser = useCallback((user) => setCurrentUserState(withAvatar(user)), []);

  // Session: load the signed-in user; drop to login when the session expires.
  useEffect(() => {
    if (!authenticated) return;
    fetchCurrentUser().then(setCurrentUser).catch(() => {});
  }, [authenticated, setCurrentUser]);
  useEffect(() => {
    const expired = () => { setAuthenticated(false); setCurrentUserState(null); };
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  }, []);

  // Badges, refreshed every 30s and on navigation.
  const refreshUnread = useCallback(() => { if (hasAccessToken()) fetchUnreadCounts().then(setUnread).catch(() => {}); }, []);
  useEffect(() => {
    if (!authenticated) return undefined;
    refreshUnread();
    const timer = window.setInterval(refreshUnread, 30000);
    return () => window.clearInterval(timer);
  }, [authenticated, page.name, refreshUnread]);

  // Browser back/forward.
  useEffect(() => {
    const onPop = () => {
      const location = parseLocation();
      postPushed.current = false;
      if (location.postId) setPostView({ postOrId: location.postId, options: {} });
      else { setPostView(null); setPage(location.page); }
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const navigate = useCallback((name, params = {}) => {
    const next = { name, ...params };
    setPage(next);
    setPostView(null);
    postPushed.current = false;
    window.history.pushState(null, '', pathFor(next));
    window.scrollTo(0, 0);
  }, []);
  const openProfile = useCallback((username) => navigate('Profile', { username }), [navigate]);
  const openPost = useCallback((postOrId, options = {}) => {
    const id = typeof postOrId === 'object' ? postOrId.id : postOrId;
    setPostView({ postOrId, options });
    if (!postPushed.current) window.history.pushState(null, '', `/post/${id}`);
    postPushed.current = true;
  }, []);
  const closePost = () => {
    setPostView(null);
    if (postPushed.current) { postPushed.current = false; window.history.back(); } else window.history.replaceState(null, '', pathFor(page));
  };

  const followStatusOf = useCallback((name, fallback = 'none') => followOverrides[name] || fallback, [followOverrides]);
  const followUser = useCallback(async (name, follow) => {
    try {
      const result = await setUserFollow(name, follow);
      setFollowOverrides((current) => ({ ...current, [name]: result.follow_status }));
      if (result.follow_status === 'requested') showToast(`Follow request sent to ${name}`);
      return result.follow_status;
    } catch (error) {
      showToast(`Follow: ${error.message}`);
      return null;
    }
  }, [showToast]);

  const logoutUser = useCallback(() => { logout(); window.location.assign('/'); }, []);

  const context = useMemo(() => ({
    currentUser, setCurrentUser, showToast, navigate, openProfile, openPost,
    openShare: (post) => setShare(post),
    openReport: (target, onReported) => setReport({ target, onReported }),
    openSheet: (actions) => setSheet(actions),
    openCreate: (type = 'post') => setCreate(type),
    openSearch: () => setSearchOpen(true),
    openChat: (person) => { setChatTarget(person); navigate('Messages'); },
    followUser, followStatusOf, refreshUnread, logoutUser,
  }), [currentUser, setCurrentUser, showToast, navigate, openProfile, openPost, followUser, followStatusOf, refreshUnread, logoutUser]);

  if (resetLink) {
    return <ResetPasswordScreen uid={resetLink.uid} token={resetLink.token} onDone={() => {
      logout();
      window.history.replaceState(null, '', '/');
      setResetLink(null);
      setAuthenticated(false);
    }}/>;
  }
  if (!authenticated) return <AuthScreen onSuccess={() => { setAuthenticated(true); refreshUnread(); }}/>;
  if (!currentUser) return <div className="app-loading"><span className="brand-word">Infogram</span></div>;

  const onCreated = (type, post) => {
    if (type === 'story') setStoriesVersion((version) => version + 1);
    else { setCreatedPost(post); if (page.name !== 'Home') navigate('Home'); }
  };
  const badge = (label) => (label === 'Messages' ? unread.messages : label === 'Notifications' ? unread.notifications : 0);
  const NAV = [
    [House, 'Home', () => navigate('Home')],
    [Search, 'Search', () => setSearchOpen(true)],
    [Compass, 'Explore', () => navigate('Explore')],
    [Clapperboard, 'Reels', () => navigate('Reels')],
    [Send, 'Messages', () => navigate('Messages')],
    [Heart, 'Notifications', () => navigate('Activity')],
    [PlusSquare, 'Create', () => setCreate('post')],
  ];
  const selected = (label) => (label === 'Notifications' ? page.name === 'Activity' : label === page.name);
  const onOwnProfile = page.name === 'Profile' && page.username === currentUser.username;

  return <AppContext.Provider value={context}>
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" onClick={(event) => { event.preventDefault(); navigate('Home'); }}><span className="brand-word">Infogram</span><Instagram className="brand-icon"/></a>
        <nav>
          {NAV.map(([Icon, label, action]) => <button key={label} className={`nav-item ${selected(label) ? 'selected' : ''}`} onClick={action}>
            <span className="nav-icon"><Icon/>{badge(label) > 0 && <i className="nav-badge">{Math.min(badge(label), 99)}</i>}</span><span>{label}</span>
          </button>)}
          <button className={`nav-item ${onOwnProfile ? 'selected' : ''}`} onClick={() => openProfile(currentUser.username)}>
            <span className="nav-icon"><img className="nav-avatar" src={currentUser.avatar} alt=""/></span><span>Profile</span>
          </button>
        </nav>
        <button className="nav-item more" onClick={logoutUser}><LogOut/><span>Log out</span></button>
      </aside>
      <main className="main-content">
        <div className="mobile-header"><span className="brand-word">Infogram</span><div>
          <button onClick={() => navigate('Activity')} aria-label="Notifications" className="nav-icon"><Heart/>{unread.notifications > 0 && <i className="nav-badge">{Math.min(unread.notifications, 99)}</i>}</button>
          <button onClick={() => navigate('Messages')} aria-label="Messages" className="nav-icon"><Send/>{unread.messages > 0 && <i className="nav-badge">{Math.min(unread.messages, 99)}</i>}</button>
        </div></div>
        {page.name === 'Home' && <HomePage createdPost={createdPost} storiesVersion={storiesVersion}/>}
        {page.name === 'Explore' && <ExplorePage topic={page.topic || ''}/>}
        {page.name === 'Reels' && <ReelsPage/>}
        {page.name === 'Messages' && <MessagesPage target={chatTarget} onTargetHandled={() => setChatTarget(null)} unreadMessages={unread.messages}/>}
        {page.name === 'Profile' && <ProfilePage key={page.username} username={page.username}/>}
      </main>
      {page.name === 'Activity' && <ActivityPage/>}
      <nav className="mobile-nav">
        <button onClick={() => navigate('Home')} aria-label="Home"><House/></button>
        <button onClick={() => setSearchOpen(true)} aria-label="Search"><Search/></button>
        <button onClick={() => setCreate('post')} aria-label="Create"><PlusSquare/></button>
        <button onClick={() => navigate('Reels')} aria-label="Reels"><Clapperboard/></button>
        <button onClick={() => openProfile(currentUser.username)} aria-label="Profile"><UserRound/></button>
      </nav>
      {postView && <PostModal key={typeof postView.postOrId === 'object' ? postView.postOrId.id : postView.postOrId} postOrId={postView.postOrId} onClose={closePost} {...postView.options}/>}
      {searchOpen && <SearchPanel onClose={() => setSearchOpen(false)}/>}
      {share && <ShareSheet post={share} onClose={() => setShare(null)}/>}
      {create && <CreateSheet initialType={create} onClose={() => setCreate(null)} onCreated={onCreated}/>}
      {report && <ReportSheet target={report.target} onClose={() => setReport(null)} onReported={(target) => { report.onReported?.(target); showToast("Thanks for reporting. We'll review it."); }}/>}
      {sheet && <ActionSheet actions={sheet} onClose={() => setSheet(null)}/>}
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  </AppContext.Provider>;
}
