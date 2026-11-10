import { useCallback, useEffect, useRef, useState } from 'react';

// Cursor-paginated list with infinite scroll.
// loader(cursorOrNull) -> { items, next }. Reloads whenever `deps` change.
export function useInfiniteList(loader, deps) {
  const [items, setItems] = useState(null);
  const [next, setNext] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const sentinelRef = useRef(null);
  const loaderRef = useRef(loader);
  const generation = useRef(0);
  const inFlight = useRef(false);
  loaderRef.current = loader;

  const load = useCallback(async (cursor) => {
    if (cursor && inFlight.current) return;
    const gen = generation.current;
    inFlight.current = true;
    setLoading(true);
    setError('');
    try {
      const page = await loaderRef.current(cursor);
      if (gen !== generation.current) return;
      setItems((current) => (cursor ? [...(current || []), ...page.items] : page.items));
      setNext(page.next);
    } catch (requestError) {
      if (gen !== generation.current) return;
      if (cursor && requestError.code === 'cursor_expired') { generation.current += 1; load(null); return; }
      setError(requestError.message);
      setNext(null);
      setItems((current) => current || []);
    } finally {
      if (gen === generation.current) { inFlight.current = false; setLoading(false); }
    }
  }, []);

  useEffect(() => {
    generation.current += 1;
    inFlight.current = false;
    setItems(null);
    setNext(null);
    load(null);
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const target = sentinelRef.current;
    if (!target || !next) return undefined;
    const observer = new IntersectionObserver(([entry]) => { if (entry.isIntersecting) load(next); }, { rootMargin: '600px' });
    observer.observe(target);
    return () => observer.disconnect();
  }, [next, load, items]);

  return { items, setItems, next, loading, error, sentinelRef, reload: () => { generation.current += 1; inFlight.current = false; load(null); } };
}

export function useDebounced(value, delay = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

// Small per-browser memory (recent searches). Never throws.
export function readStored(key, fallback) {
  try { const raw = window.localStorage.getItem(key); return raw ? JSON.parse(raw) : fallback; } catch { return fallback; }
}
export function writeStored(key, value) {
  try { window.localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable */ }
}

// Appearance: 'light' | 'dark' | 'system' (follows the device). The resolved
// theme is written to <html data-theme>, which dark.css keys off.
const THEME_KEY = 'infogram_theme';
export function applyTheme(choice) {
  const dark = choice === 'dark' || (choice === 'system' && window.matchMedia?.('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#000000' : '#ffffff');
}
export function useTheme() {
  const [theme, setThemeState] = useState(() => readStored(THEME_KEY, 'system'));
  useEffect(() => {
    applyTheme(theme);
    if (theme !== 'system' || !window.matchMedia) return undefined;
    const query = window.matchMedia('(prefers-color-scheme: dark)');
    const follow = () => applyTheme('system');
    query.addEventListener?.('change', follow);
    return () => query.removeEventListener?.('change', follow);
  }, [theme]);
  const setTheme = (next) => { writeStored(THEME_KEY, next); setThemeState(next); };
  return [theme, setTheme];
}

// "Install app": the browser's install prompt, kept until the user asks for it.
let deferredInstall = null;
const installListeners = new Set();
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferredInstall = event;
    installListeners.forEach((listener) => listener(true));
  });
  window.addEventListener('appinstalled', () => { deferredInstall = null; installListeners.forEach((listener) => listener(false)); });
}
export function useInstallPrompt() {
  const [available, setAvailable] = useState(Boolean(deferredInstall));
  useEffect(() => { installListeners.add(setAvailable); return () => installListeners.delete(setAvailable); }, []);
  const install = async () => {
    if (!deferredInstall) return false;
    deferredInstall.prompt();
    const { outcome } = await deferredInstall.userChoice;
    deferredInstall = null;
    setAvailable(false);
    return outcome === 'accepted';
  };
  return [available, install];
}

// Adaptive streaming: play the HLS playlist when there is one (native on
// Safari/iOS, hls.js elsewhere, loaded only when needed), else the MP4.
export function useVideoSource(videoRef, { hls, mp4 }) {
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;
    let player = null;
    let cancelled = false;
    if (!hls || video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = hls || mp4;
      return undefined;
    }
    import('hls.js').then(({ default: Hls }) => {
      if (cancelled) return;
      if (!Hls.isSupported()) { video.src = mp4; return; }
      player = new Hls({ capLevelToPlayerSize: true, maxBufferLength: 20 });
      player.on(Hls.Events.ERROR, (_, data) => { if (data.fatal) { player.destroy(); player = null; video.src = mp4; } });
      player.loadSource(hls);
      player.attachMedia(video);
    }).catch(() => { if (!cancelled) video.src = mp4; });
    return () => { cancelled = true; player?.destroy(); };
  }, [videoRef, hls, mp4]);
}

// Push notifications on this device.
function base64UrlToBytes(value) {
  const padded = (value + '='.repeat((4 - (value.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  return Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
}
export function usePush(api) {
  const supported = typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const [state, setState] = useState({ ready: false, enabled: false, subscribed: false, publicKey: '' });
  useEffect(() => {
    if (!supported) return;
    let cancelled = false;
    (async () => {
      try {
        const config = await api.fetchPushConfig();
        const registration = await navigator.serviceWorker.getRegistration();
        const subscription = await registration?.pushManager.getSubscription();
        if (!cancelled) setState({ ready: true, enabled: config.enabled, subscribed: Boolean(subscription) && Notification.permission === 'granted', publicKey: config.public_key });
      } catch { if (!cancelled) setState((current) => ({ ...current, ready: true })); }
    })();
    return () => { cancelled = true; };
  }, [supported]); // eslint-disable-line react-hooks/exhaustive-deps
  const toggle = async () => {
    const registration = (await navigator.serviceWorker.getRegistration()) || (await navigator.serviceWorker.register('/sw.js'));
    await navigator.serviceWorker.ready;
    if (state.subscribed) {
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) { await api.deletePushSubscription(subscription.endpoint).catch(() => {}); await subscription.unsubscribe(); }
      setState((current) => ({ ...current, subscribed: false }));
      return 'off';
    }
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return 'denied';
    const subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: base64UrlToBytes(state.publicKey) });
    await api.savePushSubscription(subscription.toJSON());
    setState((current) => ({ ...current, subscribed: true }));
    return 'on';
  };
  return { supported: supported && state.ready && state.enabled, subscribed: state.subscribed, toggle };
}
