import React, { useEffect, useState } from 'react';
import { MapPin, X } from 'lucide-react';
import { createPost, createStory, fetchLocations, normalizePost, uploadMedia } from '../api';
import { useDebounced } from '../hooks';
import { useApp } from '../context';

const MAX_BYTES = 100 * 1024 * 1024;
const ALLOWED = ['image/jpeg', 'image/png', 'image/webp', 'video/mp4', 'video/webm'];
const LIMITS = { post: 10, reel: 1, story: 1 };

// Create a post (1 file, or a 2-10 file carousel), a reel (video) or a story.
export function CreateSheet({ initialType = 'post', onClose, onCreated }) {
  const { showToast } = useApp();
  const [type, setType] = useState(initialType);
  const [files, setFiles] = useState([]);
  const [caption, setCaption] = useState('');
  const [topic, setTopic] = useState('');
  const [place, setPlace] = useState('');
  const [placeFocused, setPlaceFocused] = useState(false);
  const [placeOptions, setPlaceOptions] = useState([]);
  const placeQuery = useDebounced(place.trim());
  useEffect(() => {
    if (!placeFocused) return undefined;
    let cancelled = false;
    fetchLocations(placeQuery).then((rows) => { if (!cancelled) setPlaceOptions(rows); }).catch(() => {});
    return () => { cancelled = true; };
  }, [placeQuery, placeFocused]);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  useEffect(() => () => files.forEach((file) => URL.revokeObjectURL(file.preview)), [files]);

  const switchType = (next) => { setType(next); setFiles([]); setError(''); };
  const choose = (event) => {
    const picked = [...(event.target.files || [])];
    event.target.value = '';
    const problem = picked.find((file) => !ALLOWED.includes(file.type)) ? 'Use JPEG, PNG, WebP, MP4 or WebM files.'
      : picked.find((file) => file.size > MAX_BYTES) ? 'Each file must be 100 MB or smaller.'
      : type === 'reel' && picked.some((file) => !file.type.startsWith('video/')) ? 'Reels need a video.'
      : files.length + picked.length > LIMITS[type] ? `You can add up to ${LIMITS[type]} file${LIMITS[type] > 1 ? 's' : ''}.` : '';
    if (problem) { setError(problem); return; }
    setError('');
    setFiles((current) => [...current, ...picked.map((file) => ({ file, preview: URL.createObjectURL(file), kind: file.type.startsWith('video/') ? 'video' : 'image' }))]);
  };
  const removeFile = (index) => setFiles((current) => current.filter((_, i) => i !== index));

  const publish = async (event) => {
    event.preventDefault();
    if (!files.length || progress) return;
    setError('');
    try {
      const uploaded = [];
      for (const [index, item] of files.entries()) {
        setProgress(files.length > 1 ? `Uploading ${index + 1} of ${files.length}…` : 'Uploading…');
        uploaded.push(await uploadMedia(item.file));
      }
      setProgress('Publishing…');
      if (type === 'story') {
        await createStory({ mediaType: uploaded[0].media_type, mediaUrl: uploaded[0].media_url, caption: caption.trim().slice(0, 180) });
        showToast('Added to your story');
        onCreated?.('story');
      } else {
        const body = uploaded.length > 1
          ? { media: uploaded.map((item) => ({ media_type: item.media_type, media_url: item.media_url })) }
          : { media_type: uploaded[0].media_type, media_url: uploaded[0].media_url };
        const created = await createPost({ ...body, topic: topic.trim(), caption: caption.trim(), ...(place.trim() ? { location: place.trim() } : {}) });
        showToast(type === 'reel' ? 'Reel shared' : 'Post shared');
        onCreated?.(type, normalizePost(created));
      }
      onClose();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProgress('');
    }
  };

  const accept = type === 'reel' ? 'video/mp4,video/webm' : ALLOWED.join(',');
  return <div className="modal-backdrop create-backdrop" onClick={() => !progress && onClose()}><section className="create-sheet" onClick={(event) => event.stopPropagation()}>
    <header><b>Create new {type}</b><button onClick={onClose} disabled={Boolean(progress)} aria-label="Close create dialog"><X/></button></header>
    <div className="create-tabs">{['post', 'reel', 'story'].map((name) => <button key={name} className={type === name ? 'active-create-tab' : ''} onClick={() => switchType(name)} disabled={Boolean(progress)}>{name[0].toUpperCase() + name.slice(1)}</button>)}</div>
    {files.length
      ? <div className="create-preview">
        {files[0].kind === 'video' ? <video src={files[0].preview} controls playsInline/> : <img src={files[0].preview} alt="Selected preview"/>}
        {files.length > 1 || type === 'post'
          ? <div className="create-thumbs">
            {files.map((item, index) => <span key={item.preview}>{item.kind === 'video' ? <video src={item.preview} muted/> : <img src={item.preview} alt=""/>}<button onClick={() => removeFile(index)} aria-label="Remove file">×</button></span>)}
            {files.length < LIMITS[type] && <label className="create-add-more"><input type="file" accept={accept} multiple onChange={choose}/>+</label>}
          </div>
          : <button onClick={() => setFiles([])}>Choose another file</button>}
      </div>
      : <label className="upload-drop"><input type="file" accept={accept} multiple={type === 'post'} onChange={choose}/><span className="upload-icon">＋</span>
        <b>{type === 'reel' ? 'Select a video' : type === 'story' ? 'Select a photo or video' : 'Select photos or videos'}</b>
        <small>{type === 'post' ? 'Add up to 10 to make a carousel' : type === 'story' ? 'Stories disappear after 24 hours' : 'Share a short, useful video'}</small></label>}
    <form className="create-form" onSubmit={publish}>
      {type !== 'story' && <input value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="Topic (e.g. Personal finance)" maxLength="80"/>}
      {type !== 'story' && <div className="location-input">
        <MapPin/>
        <input value={place} onChange={(event) => setPlace(event.target.value)} onFocus={() => setPlaceFocused(true)} onBlur={() => window.setTimeout(() => setPlaceFocused(false), 150)}
          placeholder="Add location" maxLength="100" aria-label="Add location"/>
        {place && <button type="button" onClick={() => setPlace('')} aria-label="Remove location"><X/></button>}
        {placeFocused && placeOptions.filter((option) => option.name.toLowerCase() !== place.trim().toLowerCase()).length > 0 && <div className="location-options">
          {placeOptions.filter((option) => option.name.toLowerCase() !== place.trim().toLowerCase()).slice(0, 6).map((option) => <button type="button" key={option.slug} onMouseDown={(event) => event.preventDefault()} onClick={() => { setPlace(option.name); setPlaceFocused(false); }}>
            <b>{option.name}</b><small>{option.post_count} {option.post_count === 1 ? 'post' : 'posts'}</small>
          </button>)}
        </div>}
      </div>}
      <textarea value={caption} onChange={(event) => setCaption(event.target.value)} placeholder={type === 'story' ? 'Add a caption (optional)' : 'Write a caption… use #hashtags'} rows="3" maxLength={type === 'story' ? 180 : 2200}/>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <div className="create-footer"><span>{progress || (type === 'story' ? 'Visible to your followers for 24h' : 'Informative content only')}</span><button disabled={!files.length || Boolean(progress)}>{progress ? 'Please wait…' : 'Share'}</button></div>
    </form>
  </section></div>;
}
