import React, { useEffect, useRef, useState } from 'react';
import { Smile } from 'lucide-react';

const EMOJIS = ['😂', '😍', '🔥', '👏', '🙌', '💯', '❤️', '😮', '😢', '🤔', '🙏', '👍', '🎉', '✨', '💡', '📚', '🚀', '✅', '👀', '😊', '🤝', '💪', '🧠', '📌'];

// Emoji popover for comment and message inputs. onPick(emoji) inserts at the caret.
export function EmojiButton({ onPick, placement = 'up' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = (event) => { if (!ref.current?.contains(event.target)) setOpen(false); };
    const escape = (event) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', escape); };
  }, [open]);
  return <span className="emoji-wrap" ref={ref}>
    <button type="button" className="emoji-toggle" onClick={() => setOpen((value) => !value)} aria-label="Add emoji" aria-expanded={open}><Smile/></button>
    {open && <span className={`emoji-popover ${placement}`} role="dialog" aria-label="Emoji">
      {EMOJIS.map((emoji) => <button type="button" key={emoji} onClick={() => onPick(emoji)}>{emoji}</button>)}
    </span>}
  </span>;
}

// Insert text at an input's caret (or the end) and keep focus there.
export function insertAtCaret(input, value, text, setValue) {
  const start = input?.selectionStart ?? value.length;
  const end = input?.selectionEnd ?? value.length;
  const next = value.slice(0, start) + text + value.slice(end);
  setValue(next);
  window.requestAnimationFrame(() => {
    if (!input) return;
    input.focus();
    input.setSelectionRange(start + text.length, start + text.length);
  });
}
