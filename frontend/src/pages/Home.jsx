import React, { useCallback, useEffect, useState } from 'react';
import { fetchFeedPage, fetchStoryTray, fetchSuggestions } from '../api';
import { useApp } from '../context';
import { useInfiniteList } from '../hooks';
import { PostCard } from '../components/PostCard';
import { FollowButton, PeopleModal } from '../components/Sheets';
import { StoryTray, StoryViewer } from '../components/Stories';

export function HomePage({ createdPost, storiesVersion }) {
  const { currentUser, openProfile, openCreate, navigate, logoutUser } = useApp();
  const feed = useInfiniteList((cursor) => fetchFeedPage(cursor), []);
  const [stories, setStories] = useState([]);
  const [viewerIndex, setViewerIndex] = useState(null);
  const [suggestions, setSuggestions] = useState(null);
  const [allSuggestions, setAllSuggestions] = useState(false);

  const loadStories = useCallback(() => { fetchStoryTray().then(setStories).catch(() => setStories([])); }, []);
  useEffect(loadStories, [loadStories, storiesVersion]);
  useEffect(() => { fetchSuggestions(5).then(setSuggestions).catch(() => setSuggestions([])); }, []);
  // A post you just created appears at the top.
  useEffect(() => {
    if (createdPost) feed.setItems((current) => [createdPost, ...(current || []).filter((post) => post.id !== createdPost.id)]);
  }, [createdPost]); // eslint-disable-line react-hooks/exhaustive-deps

  const dropPost = (post) => feed.setItems((current) => current.filter((item) => item.id !== post.id));
  const bumpComments = (postId) => feed.setItems((current) => current.map((item) => (item.id === postId ? { ...item, commentCount: item.commentCount + 1 } : item)));
  const posts = feed.items || [];

  return <>
    <div className="feed-column">
      <StoryTray groups={stories} onOpen={setViewerIndex}/>
      {feed.items === null && <div className="feed-skeleton"><div/><div/></div>}
      {feed.items !== null && !posts.length && !feed.error && <div className="empty-state">
        <b>Welcome to Infogram</b><p>Follow creators to fill your feed with useful posts, or share your first one.</p>
        <div><button onClick={() => navigate('Explore')}>Explore creators</button><button onClick={() => openCreate('post')}>Create a post</button></div>
      </div>}
      {posts.map((post) => <PostCard key={post.id} post={post} onHidden={dropPost} onDeleted={dropPost} onCommentAdded={bumpComments}/>)}
      {feed.error && <div className="empty-state"><p>{feed.error}</p><button onClick={feed.reload}>Try again</button></div>}
      <div ref={feed.sentinelRef} className="scroll-sentinel">{feed.loading && feed.items !== null ? 'Loading more…' : posts.length > 0 && !feed.next ? "You're all caught up" : ''}</div>
    </div>
    <aside className="right-rail">
      {currentUser && <div className="account-row">
        <button className="avatar-button" onClick={() => openProfile(currentUser.username)}><img src={currentUser.avatar} alt=""/></button>
        <div><b role="button" tabIndex={0} onClick={() => openProfile(currentUser.username)}>{currentUser.username}</b><span>{currentUser.bio ? currentUser.bio.slice(0, 40) : 'Add a bio to your profile'}</span></div>
        <button onClick={logoutUser}>Log out</button>
      </div>}
      {suggestions?.length > 0 && <>
        <div className="suggestions-title"><b>Suggested for you</b><button onClick={() => setAllSuggestions(true)}>See all</button></div>
        {suggestions.map((person) => <div className="suggestion" key={person.name}>
          <button className="avatar-button" onClick={() => openProfile(person.name)}><img src={person.avatar} alt=""/></button>
          <div><b role="button" tabIndex={0} onClick={() => openProfile(person.name)}>{person.name}</b><span>{person.reason}</span></div>
          <FollowButton name={person.name} initialStatus={person.followStatus} className="suggestion-follow"/>
        </div>)}
      </>}
      <footer>© 2026 INFOGRAM · Learn something useful in every scroll</footer>
    </aside>
    {viewerIndex !== null && <StoryViewer groups={stories} startIndex={viewerIndex} onClose={() => { setViewerIndex(null); loadStories(); }}
      onChanged={(change) => { if (change?.reload) loadStories(); else setStories((current) => [...current]); }}/>}
    {allSuggestions && <PeopleModal title="Suggested for you" load={() => fetchSuggestions(30)} emptyText="No suggestions right now." onClose={() => setAllSuggestions(false)}/>}
  </>;
}
