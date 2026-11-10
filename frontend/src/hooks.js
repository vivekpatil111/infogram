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
