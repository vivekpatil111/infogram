const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

// ---------------------------------------------------------------------------
// Session
// ---------------------------------------------------------------------------

export const hasAccessToken = () => Boolean(window.localStorage.getItem('infogram_access_token'));
const getAccessToken = () => window.localStorage.getItem('infogram_access_token');

// Fired when the session can't be refreshed; App listens and shows the login screen.
export const SESSION_EXPIRED_EVENT = 'infogram:session-expired';

function clearTokens() {
  window.localStorage.removeItem('infogram_access_token');
  window.localStorage.removeItem('infogram_refresh_token');
}

export function logout() {
  const refresh = window.localStorage.getItem('infogram_refresh_token');
  clearTokens();
  // Best effort: blacklist the refresh token server-side.
  if (refresh) {
    fetch(`${API_BASE_URL}/auth/logout/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ refresh }),
    }).catch(() => {});
  }
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

const AVATAR_COLORS = ['#0095f6', '#e1306c', '#833ab4', '#f77737', '#2e7d32', '#00897b', '#5c6bc0', '#c2185b'];

// Initials avatar for accounts without a photo (no third-party placeholder images).
export function defaultAvatar(name = '?') {
  const clean = String(name || '?');
  const hash = [...clean].reduce((total, char) => (total * 31 + char.charCodeAt(0)) >>> 0, 7);
  const initials = clean.replace(/[^a-zA-Z0-9]/g, ' ').trim().split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase() || '?';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="${AVATAR_COLORS[hash % AVATAR_COLORS.length]}"/><text x="50" y="50" dy=".35em" text-anchor="middle" font-family="Arial,sans-serif" font-size="40" font-weight="700" fill="#fff">${initials}</text></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export const avatarOf = (user) => user?.avatar_url || defaultAvatar(user?.username);

export function relativeTime(value) {
  if (!value) return 'now';
  const minutes = Math.floor(Math.max(0, Date.now() - new Date(value).getTime()) / 60000);
  if (minutes < 1) return 'now';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return `${Math.floor(days / 7)}w`;
}

export function formatCount(value) {
  const number = Number(value) || 0;
  if (number < 1000) return String(number);
  if (number < 1000000) return `${(number / 1000).toFixed(1).replace('.0', '')}K`;
  return `${(number / 1000000).toFixed(1).replace('.0', '')}M`;
}

export const postLink = (postId) => `${window.location.origin}/post/${postId}`;

// ---------------------------------------------------------------------------
// HTTP
// ---------------------------------------------------------------------------

// One in-flight refresh shared by concurrent 401s (refresh tokens rotate, so
// two parallel refreshes would invalidate each other).
let refreshPromise = null;

function refreshAccessToken() {
  const refresh = window.localStorage.getItem('infogram_refresh_token');
  if (!refresh) return Promise.resolve(false);
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ refresh }),
    })
      .then(async (response) => {
        if (!response.ok) return false;
        const tokens = await response.json();
        window.localStorage.setItem('infogram_access_token', tokens.access);
        if (tokens.refresh) window.localStorage.setItem('infogram_refresh_token', tokens.refresh);
        return true;
      })
      .catch(() => false)
      .finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

async function apiRequest(path, options = {}, retried = false) {
  const token = getAccessToken();
  const headers = new Headers(options.headers || {});
  headers.set('Accept', 'application/json');
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new Error(`Can't reach the server at ${API_BASE_URL}. Is the backend running?`);
  }
  if (response.status === 401 && token && !retried && !path.startsWith('/auth/login') && !path.startsWith('/auth/password-reset')) {
    if (await refreshAccessToken()) return apiRequest(path, options, true);
    clearTokens();
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    throw new Error('Your session expired. Please log in again.');
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const fieldError = Object.values(payload).flat().find((value) => typeof value === 'string');
    const error = new Error(payload.detail || fieldError || 'Something went wrong. Please try again.');
    error.status = response.status;
    error.code = payload.code;
    throw error;
  }
  return payload;
}

// Ranked feeds page through a server-side snapshot: follow `next` as-is.
function pathFromNext(next) {
  const url = new URL(next);
  const base = new URL(API_BASE_URL);
  return url.pathname.slice(base.pathname.length) + url.search;
}

// ---------------------------------------------------------------------------
// Normalisers (API shape -> UI shape)
// ---------------------------------------------------------------------------

export function normalizePost(post) {
  return {
    id: post.id,
    authorId: post.author?.id,
    name: post.author?.username || 'unknown',
    avatar: avatarOf(post.author),
    followStatus: post.author?.follow_status || 'none',
    verified: Boolean(post.author?.is_verified),
    expertTitle: post.author?.expert_title || '',
    place: post.topic || '',
    vertical: post.vertical || '',
    resources: post.resources || [],
    paths: post.paths || [],
    seenByMe: Boolean(post.seen_by_me),
    location: post.location || null, // { name, slug }
    image: post.media_url,
    poster: post.thumbnail_url || '',
    hls: post.hls_url || '',
    mediaType: post.media_type,
    slides: (post.media || []).map((slide) => ({ url: slide.media_url, type: slide.media_type, poster: slide.thumbnail_url || '' })),
    caption: post.caption || '',
    hashtags: post.hashtags || [],
    time: relativeTime(post.created_at),
    likeCount: post.like_count || 0,
    commentCount: post.comment_count || 0,
    likedByMe: Boolean(post.liked_by_me),
    savedByMe: Boolean(post.saved_by_me),
    isSuggested: Boolean(post.is_suggested),
  };
}

export function normalizeComment(comment) {
  return {
    id: comment.id,
    authorId: comment.author.id,
    name: comment.author.username,
    avatar: avatarOf(comment.author),
    text: comment.text,
    time: relativeTime(comment.created_at),
    parentId: comment.parent_id || null,
    likeCount: comment.like_count || 0,
    replyCount: comment.reply_count || 0,
    likedByMe: Boolean(comment.liked_by_me),
  };
}

export function normalizeMessage(message, currentUserId) {
  return {
    id: message.id,
    from: message.sender?.id === currentUserId ? 'me' : 'them',
    text: message.body,
    time: relativeTime(message.created_at),
  };
}

const userRow = (user) => ({
  id: user.id,
  name: user.username,
  avatar: avatarOf(user),
  bio: user.bio || '',
  followers: user.followers_count || 0,
  followStatus: user.follow_status || (user.is_following ? 'following' : user.is_requested ? 'requested' : 'none'),
  isPrivate: Boolean(user.is_private),
  joined: user.date_joined || null,
  verified: Boolean(user.is_verified),
});

// ---------------------------------------------------------------------------
// Auth & account
// ---------------------------------------------------------------------------

// Returns { twoFactor: { challenge } } when the account uses two-step login;
// call verifyTwoFactor(challenge, code) next.
export async function login(username, password) {
  const response = await apiRequest('/auth/login/', { method: 'POST', body: JSON.stringify({ username, password }) });
  if (response.two_factor_required) return { twoFactor: { challenge: response.challenge } };
  storeTokens(response);
  return response;
}

function storeTokens(response) {
  window.localStorage.setItem('infogram_access_token', response.access);
  if (response.refresh) window.localStorage.setItem('infogram_refresh_token', response.refresh);
}

export async function verifyTwoFactor(challenge, code) {
  const response = await apiRequest('/auth/2fa/verify/', { method: 'POST', body: JSON.stringify({ challenge, code: code.trim() }) });
  storeTokens(response);
  return response;
}

export const fetchTwoFactor = () => apiRequest('/auth/2fa/');
export const twoFactorStep = (step, body = {}) => apiRequest(`/auth/2fa/${step}/`, { method: 'POST', body: JSON.stringify(body) });

export const register = ({ username, email, password }) =>
  apiRequest('/auth/register/', { method: 'POST', body: JSON.stringify({ username, email, password }) });

export const fetchCurrentUser = () => apiRequest('/auth/me/');
export const updateProfile = (profile) => apiRequest('/auth/me/', { method: 'PATCH', body: JSON.stringify(profile) });

export async function changePassword(currentPassword, newPassword) {
  const response = await apiRequest('/auth/password/change/', {
    method: 'POST',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  window.localStorage.setItem('infogram_access_token', response.access);
  window.localStorage.setItem('infogram_refresh_token', response.refresh);
  return response;
}

export const requestPasswordReset = (email) =>
  apiRequest('/auth/password-reset/', { method: 'POST', body: JSON.stringify({ email }) });

export const confirmPasswordReset = (uid, token, newPassword) =>
  apiRequest('/auth/password-reset/confirm/', { method: 'POST', body: JSON.stringify({ uid, token, new_password: newPassword }) });

// ---------------------------------------------------------------------------
// Media
// ---------------------------------------------------------------------------

export async function uploadMedia(file) {
  const presign = await apiRequest('/media/presign/', {
    method: 'POST',
    body: JSON.stringify({ filename: file.name, content_type: file.type, size_bytes: file.size }),
  });
  let uploadResponse;
  try {
    uploadResponse = await fetch(presign.upload_url, {
      method: 'PUT',
      headers: {
        ...presign.headers,
        ...(presign.local_upload && getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : {}),
      },
      body: file,
    });
  } catch {
    // The upload goes straight to object storage, not to our API, so a network
    // failure here means this device can't reach the storage host (DNS, firewall,
    // flaky connection) even though the API itself is fine.
    throw new Error(`Couldn't reach media storage (${new URL(presign.upload_url).host}). Check your connection or DNS and try again.`);
  }
  if (!uploadResponse.ok) {
    const payload = await uploadResponse.json().catch(() => ({}));
    throw new Error(payload.detail || 'Media upload failed. Please try again.');
  }
  return presign;
}

// ---------------------------------------------------------------------------
// Posts, feeds, comments
// ---------------------------------------------------------------------------

export const createPost = (post) => apiRequest('/posts/', { method: 'POST', body: JSON.stringify(post) });
export const deletePost = (postId) => apiRequest(`/posts/${postId}/`, { method: 'DELETE' });
export const fetchPost = async (postId) => normalizePost(await apiRequest(`/posts/${postId}/`));

export async function fetchFeedPage(next = null) {
  const response = await apiRequest(next ? pathFromNext(next) : '/feed/');
  return { items: response.results.map(normalizePost), next: response.next };
}

export async function fetchReelsPage(feed = 'for_you', next = null) {
  const response = await apiRequest(next ? pathFromNext(next) : `/reels/?feed=${encodeURIComponent(feed)}`);
  return { items: response.results.map(normalizePost), next: response.next };
}

export async function fetchExplorePage(topic = '', next = null, vertical = '') {
  const params = new URLSearchParams();
  if (topic) params.set('topic', topic);
  if (vertical) params.set('vertical', vertical);
  const query = params.toString() ? `?${params}` : '';
  const response = await apiRequest(next ? pathFromNext(next) : `/explore/${query}`);
  return { items: response.results.map(normalizePost), next: response.next };
}

export async function fetchTopics() {
  return (await apiRequest('/topics/')).topics || [];
}

export const setPostLike = (postId, liked) => apiRequest(`/posts/${postId}/like/`, { method: liked ? 'POST' : 'DELETE' });
export const setPostSaved = (postId, saved) => apiRequest(`/posts/${postId}/save/`, { method: saved ? 'POST' : 'DELETE' });

// Top-level comments, or the replies under one comment when parentId is given.
export async function fetchComments(postId, parentId = null) {
  const response = await apiRequest(`/posts/${postId}/comments/?limit=100${parentId ? `&parent=${parentId}` : ''}`);
  return response.results.map(normalizeComment);
}

export const setCommentLike = (postId, commentId, like) =>
  apiRequest(`/posts/${postId}/comments/${commentId}/like/`, { method: like ? 'POST' : 'DELETE' });

export async function addPostComment(postId, text, parentId = null) {
  return normalizeComment(await apiRequest(`/posts/${postId}/comments/`, { method: 'POST', body: JSON.stringify(parentId ? { text, parent_id: parentId } : { text }) }));
}

export const deleteComment = (postId, commentId) => apiRequest(`/posts/${postId}/comments/${commentId}/`, { method: 'DELETE' });

// ---------------------------------------------------------------------------
// Stories
// ---------------------------------------------------------------------------

export async function fetchStoryTray() {
  const response = await apiRequest('/stories/');
  return response.results.map((group) => ({
    authorId: group.author.id,
    name: group.author.username,
    avatar: avatarOf(group.author),
    isOwn: Boolean(group.is_own),
    hasUnseen: Boolean(group.has_unseen),
    resumeIndex: group.resume_index || 0,
    stories: group.stories.map((story) => ({
      id: story.id,
      media: story.media_url,
      mediaType: story.media_type,
      caption: story.caption || '',
      time: relativeTime(story.created_at),
      viewed: Boolean(story.viewed_by_me),
      stickers: story.stickers || [],
    })),
  }));
}

export const createStory = ({ mediaType, mediaUrl, caption = '', stickers = [] }) =>
  apiRequest('/stories/', { method: 'POST', body: JSON.stringify({ media_type: mediaType, media_url: mediaUrl, caption, stickers }) });
// Answer a story poll; returns the story with counts once you've voted.
export const voteStoryPoll = (storyId, option) =>
  apiRequest(`/stories/${storyId}/vote/`, { method: 'POST', body: JSON.stringify({ option }) });
export const reportProblem = (message) =>
  apiRequest('/support/problems/', { method: 'POST', body: JSON.stringify({ message, page: window.location.pathname }) });
export const deleteStory = (storyId) => apiRequest(`/stories/${storyId}/`, { method: 'DELETE' });
export const markStoryViewed = (storyId) => apiRequest(`/stories/${storyId}/view/`, { method: 'POST' });

export async function fetchStoryViewers(storyId) {
  const response = await apiRequest(`/stories/${storyId}/viewers/`);
  return response.results.map((viewer) => ({ id: viewer.id, name: viewer.username, avatar: avatarOf(viewer), time: relativeTime(viewer.viewed_at) }));
}

// ---------------------------------------------------------------------------
// People
// ---------------------------------------------------------------------------

export async function fetchProfile(username, tab = 'posts') {
  const response = await apiRequest(`/users/${encodeURIComponent(username)}/profile/?tab=${tab}&limit=50`);
  return { profile: response.profile, items: response.results.map(normalizePost) };
}

export const setUserFollow = (username, follow) =>
  apiRequest(`/users/${encodeURIComponent(username)}/follow/`, { method: follow ? 'POST' : 'DELETE' });

export async function fetchFollowList(username, kind) {
  const response = await apiRequest(`/users/${encodeURIComponent(username)}/${kind}/?limit=50`);
  return response.results.map(userRow);
}

export async function fetchLikers(postId) {
  const response = await apiRequest(`/posts/${postId}/likers/?limit=50`);
  return response.results.map(userRow);
}

export async function fetchSuggestions(limit = 5) {
  const response = await apiRequest(`/users/suggested/?limit=${limit}`);
  return response.results.map((user) => ({
    ...userRow(user),
    reason: user.followed_by ? `Followed by ${user.followed_by}` : user.is_private ? 'Private account' : 'Suggested for you',
  }));
}

export const acceptFollowRequest = (username) => apiRequest(`/follow-requests/${encodeURIComponent(username)}/accept/`, { method: 'POST' });
export const declineFollowRequest = (username) => apiRequest(`/follow-requests/${encodeURIComponent(username)}/decline/`, { method: 'POST' });

export async function searchContent(query) {
  const response = await apiRequest(`/search/?q=${encodeURIComponent(query)}&type=all`);
  return {
    users: (response.users || []).map(userRow),
    hashtags: response.hashtags || [],
    locations: response.locations || [],
    posts: (response.posts || []).map(normalizePost),
  };
}

// Places to tag a post with (most used first), and a place's page.
export async function fetchLocations(query = '') {
  const response = await apiRequest(`/locations/?q=${encodeURIComponent(query)}`);
  return response.results;
}

export async function fetchLocationPage(slug, next = null) {
  const response = await apiRequest(next ? pathFromNext(next) : `/locations/${encodeURIComponent(slug)}/`);
  return { location: response.location, items: response.results.map(normalizePost), next: response.next };
}

// ---------------------------------------------------------------------------
// Activity
// ---------------------------------------------------------------------------

export async function fetchNotifications() {
  const response = await apiRequest('/notifications/');
  return (response.results || response).map((item) => ({
    id: item.id,
    name: item.actor.username,
    avatar: avatarOf(item.actor),
    text: item.text,
    createdAt: item.created_at,
    time: relativeTime(item.created_at),
    // The activity filters use 'request' for follow requests.
    type: item.notification_type === 'follow_request' ? 'request' : item.notification_type,
    postId: item.post_id,
    image: item.post_thumbnail_url || '',
    unread: !item.read_at,
  }));
}

export const markNotificationRead = (id) => apiRequest(`/notifications/${id}/read/`, { method: 'POST' });
export const markAllNotificationsRead = () => apiRequest('/notifications/read-all/', { method: 'POST' });
export const fetchUnreadCounts = () => apiRequest('/notifications/unread-count/');

// ---------------------------------------------------------------------------
// Messages
// ---------------------------------------------------------------------------

export async function fetchConversations(currentUserId) {
  const response = await apiRequest('/conversations/');
  return response.map((conversation) => {
    const others = conversation.participants.filter((item) => item.id !== currentUserId);
    const participant = others[0] || conversation.participants[0];
    const last = conversation.last_message;
    return {
      id: conversation.id,
      name: others.length > 1 ? others.map((item) => item.username).join(', ') : participant?.username || 'Conversation',
      avatar: avatarOf(participant),
      participantId: participant?.id,
      preview: last ? `${last.sender?.id === currentUserId ? 'You: ' : ''}${last.body}` : 'Start a conversation',
      time: relativeTime(last?.created_at || conversation.updated_at),
      unreadCount: conversation.unread_count || 0,
      loaded: false,
      messages: last ? [normalizeMessage(last, currentUserId)] : [],
    };
  });
}

export const createConversation = (participantIds) =>
  apiRequest('/conversations/', { method: 'POST', body: JSON.stringify({ participant_ids: participantIds }) });

export async function sendConversationMessage(conversationId, body, currentUserId) {
  return normalizeMessage(
    await apiRequest(`/conversations/${conversationId}/messages/`, { method: 'POST', body: JSON.stringify({ body }) }),
    currentUserId,
  );
}

// Full history, oldest first (the API pages newest first).
export async function fetchMessages(conversationId, currentUserId) {
  const response = await apiRequest(`/conversations/${conversationId}/messages/?limit=100`);
  return response.results.map((message) => normalizeMessage(message, currentUserId)).reverse();
}

export const markConversationRead = (conversationId) => apiRequest(`/conversations/${conversationId}/read/`, { method: 'POST' });

// Live chat. Refreshes the access token first (a stale one closes the socket
// with 4403), then calls onMessage(rawMessage) for every broadcast message.
export async function openConversationSocket(conversationId, onMessage) {
  await apiRequest('/auth/me/');
  const wsBase = API_BASE_URL.replace(/^http/, 'ws').replace(/\/api\/v1\/?$/, '');
  const socket = new WebSocket(`${wsBase}/ws/conversations/${conversationId}/?token=${encodeURIComponent(getAccessToken())}`);
  socket.addEventListener('message', (event) => {
    try { onMessage(JSON.parse(event.data)); } catch { /* ignore malformed frames */ }
  });
  return socket;
}

// ---------------------------------------------------------------------------
// Safety
// ---------------------------------------------------------------------------

export const setUserBlocked = (username, blocked) =>
  apiRequest(`/users/${encodeURIComponent(username)}/block/`, { method: blocked ? 'POST' : 'DELETE' });

// Partial update: pass only what changes, e.g. { stories: true }. Both false unmutes.
export function setUserMuted(username, changes) {
  if (changes.posts === false && changes.stories === false) return apiRequest(`/users/${encodeURIComponent(username)}/mute/`, { method: 'DELETE' });
  return apiRequest(`/users/${encodeURIComponent(username)}/mute/`, { method: 'POST', body: JSON.stringify(changes) });
}

// Same values as the backend's Report.Reason choices.
export const REPORT_REASONS = [
  ['spam', "It's spam"],
  ['false_information', 'False or misleading information'],
  ['scam', 'Scam or fraud'],
  ['harassment', 'Bullying or harassment'],
  ['hate', 'Hate speech or symbols'],
  ['violence', 'Violence or dangerous organisations'],
  ['nudity', 'Nudity or sexual activity'],
  ['self_harm', 'Suicide or self-injury'],
  ['intellectual_property', 'Intellectual property violation'],
  ['impersonation', 'Pretending to be someone else'],
  ['other', 'Something else'],
];

export const reportContent = ({ targetType, targetId, reason, details = '' }) =>
  apiRequest('/reports/', { method: 'POST', body: JSON.stringify({ target_type: targetType, target_id: String(targetId), reason, details }) });

export async function fetchBlockedAccounts() {
  const response = await apiRequest('/blocks/');
  return response.results.map((user) => ({ id: user.id, name: user.username, avatar: avatarOf(user), bio: 'Blocked', followers: 0, followStatus: 'none' }));
}

// ---------------------------------------------------------------------------
// Knowledge features: verticals, seen tracking, resources, paths, experts
// ---------------------------------------------------------------------------

let verticalsPromise = null;
// The fixed Knowledge Verticals, fetched once per session.
export function fetchVerticals() {
  verticalsPromise = verticalsPromise || apiRequest('/verticals/').then((response) => response.results).catch((error) => { verticalsPromise = null; throw error; });
  return verticalsPromise;
}

// Posts that were really on screen, sent in small batches (first view counts).
const seenQueue = new Set();
const seenSent = new Set();
let seenTimer = null;
function flushSeen() {
  seenTimer = null;
  const ids = [...seenQueue].slice(0, 100);
  ids.forEach((id) => { seenQueue.delete(id); seenSent.add(id); });
  if (ids.length && hasAccessToken()) apiRequest('/posts/seen/', { method: 'POST', body: JSON.stringify({ ids }) }).catch(() => ids.forEach((id) => seenSent.delete(id)));
}
export function markSeen(postId) {
  if (!postId || seenSent.has(postId) || seenQueue.has(postId)) return;
  seenQueue.add(postId);
  if (!seenTimer) seenTimer = window.setTimeout(flushSeen, 2000);
}
if (typeof document !== 'undefined') document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden' && seenQueue.size) flushSeen(); });

export const openResource = (postId, resourceId) =>
  apiRequest(`/posts/${postId}/resources/${resourceId}/open/`, { method: 'POST' }).catch(() => {});

export const fetchPaths = (creator) => apiRequest(`/paths/?creator=${encodeURIComponent(creator)}`);
export async function fetchPath(pathId) {
  const path = await apiRequest(`/paths/${pathId}/`);
  return { ...path, lessons: (path.lessons || []).map(normalizePost) };
}
export const savePath = (path, pathId = null) =>
  apiRequest(pathId ? `/paths/${pathId}/` : '/paths/', { method: pathId ? 'PATCH' : 'POST', body: JSON.stringify(path) });
export const deletePath = (pathId) => apiRequest(`/paths/${pathId}/`, { method: 'DELETE' });

export const fetchExpertStatus = () => apiRequest('/auth/expert-application/');
export const applyForExpert = (application) =>
  apiRequest('/auth/expert-application/', { method: 'POST', body: JSON.stringify(application) });

// ---------------------------------------------------------------------------
// Push notifications, tips
// ---------------------------------------------------------------------------

export const fetchPushConfig = () => apiRequest('/notifications/push/');
export const savePushSubscription = (subscription) =>
  apiRequest('/notifications/push/', { method: 'POST', body: JSON.stringify(subscription) });
export const deletePushSubscription = (endpoint) =>
  apiRequest('/notifications/push/', { method: 'DELETE', body: JSON.stringify({ endpoint }) });

let tipConfigPromise = null;
export function fetchTipConfig() {
  tipConfigPromise = tipConfigPromise || apiRequest('/tips/config/').catch((error) => { tipConfigPromise = null; throw error; });
  return tipConfigPromise;
}
export const createTip = ({ creator, amount, postId, message }) =>
  apiRequest('/tips/', { method: 'POST', body: JSON.stringify({ creator, amount, post_id: postId || null, message }) });
export const verifyTip = (payment) => apiRequest('/tips/verify/', { method: 'POST', body: JSON.stringify(payment) });
export const fetchTips = (direction) => apiRequest(`/tips/${direction}/`);
