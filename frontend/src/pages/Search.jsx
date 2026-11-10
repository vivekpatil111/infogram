import React, { useEffect, useState } from 'react';
import { Hash, Search, X } from 'lucide-react';
import { searchContent } from '../api';
import { useApp } from '../context';
import { readStored, useDebounced, writeStored } from '../hooks';

const RECENT_KEY = 'infogram_recent_searches';

// Slide-over search: people and hashtags, with recent searches kept in this browser.
export function SearchPanel({ onClose }) {
  const { openProfile, navigate } = useApp();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [recent, setRecent] = useState(() => readStored(RECENT_KEY, []));
  const term = useDebounced(query.trim());

  useEffect(() => {
    if (term.replace(/^[#@]/, '').length < 2) { setResults(null); return undefined; }
    let cancelled = false;
    setLoading(true);
    searchContent(term)
      .then((response) => { if (!cancelled) setResults(response); })
      .catch(() => { if (!cancelled) setResults({ users: [], hashtags: [], posts: [] }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [term]);

  const remember = (entry) => {
    const next = [entry, ...recent.filter((item) => !(item.kind === entry.kind && item.name === entry.name))].slice(0, 12);
    setRecent(next);
    writeStored(RECENT_KEY, next);
  };
  const forget = (entry) => {
    const next = recent.filter((item) => !(item.kind === entry.kind && item.name === entry.name));
    setRecent(next);
    writeStored(RECENT_KEY, next);
  };
  const pick = (entry) => {
    remember(entry);
    onClose();
    if (entry.kind === 'user') openProfile(entry.name); else navigate('Explore', { topic: `#${entry.name}` });
  };

  const people = results?.users || [];
  const tags = results?.hashtags || [];
  return <div className="search-backdrop" onClick={onClose}><section className="search-panel" onClick={(event) => event.stopPropagation()}>
    <header>
      <div className="search-input-wrap"><Search/><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search people or #hashtags"/>
        {query && <button className="clear-search" onClick={() => setQuery('')} aria-label="Clear search"><X/></button>}</div>
      <button className="cancel-search" onClick={onClose}>Cancel</button>
    </header>
    <div className="search-panel-body">
      {results === null
        ? <>
          <div className="search-recent-heading"><b>Recent</b>{recent.length > 0 && <button onClick={() => { setRecent([]); writeStored(RECENT_KEY, []); }}>Clear all</button>}</div>
          {!recent.length && <p className="search-empty">Search for creators, topics and #hashtags.</p>}
          {recent.map((entry) => <div className="search-result recent" key={`${entry.kind}-${entry.name}`}>
            <button onClick={() => pick(entry)}>{entry.kind === 'user' ? <img src={entry.avatar} alt=""/> : <span className="hashtag-icon"><Hash/></span>}<span><b>{entry.kind === 'tag' ? `#${entry.name}` : entry.name}</b><small>{entry.detail}</small></span></button>
            <button className="recent-remove" onClick={() => forget(entry)} aria-label="Remove from recent"><X/></button>
          </div>)}
        </>
        : <>
          {loading && <p className="search-empty">Searching…</p>}
          {tags.map((tag) => <button className="search-result" key={`tag-${tag.name}`} onClick={() => pick({ kind: 'tag', name: tag.name, detail: `${tag.post_count} posts` })}>
            <span className="hashtag-icon"><Hash/></span><span><b>#{tag.name}</b><small>{tag.post_count} {tag.post_count === 1 ? 'post' : 'posts'}</small></span></button>)}
          {people.map((person) => <button className="search-result" key={`user-${person.name}`} onClick={() => pick({ kind: 'user', name: person.name, avatar: person.avatar, detail: person.bio || `${person.followers} followers` })}>
            <img src={person.avatar} alt=""/><span><b>{person.name}</b><small>{person.followStatus === 'following' ? 'Following' : person.bio || `${person.followers} followers`}</small></span></button>)}
          {!loading && !people.length && !tags.length && <p className="no-results">No results for "{term}".</p>}
        </>}
    </div>
  </section></div>;
}
