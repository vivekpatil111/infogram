import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { HandCoins, X } from 'lucide-react';
import { avatarOf, createTip, fetchTipConfig, fetchTips, relativeTime, verifyTip } from '../api';
import { useApp } from '../context';
import { ListSkeleton } from './Skeleton';

const CHECKOUT_SRC = 'https://checkout.razorpay.com/v1/checkout.js';
let checkoutPromise = null;
function loadCheckout() {
  checkoutPromise = checkoutPromise || new Promise((resolve, reject) => {
    if (window.Razorpay) { resolve(window.Razorpay); return; }
    const script = document.createElement('script');
    script.src = CHECKOUT_SRC;
    script.onload = () => resolve(window.Razorpay);
    script.onerror = () => { checkoutPromise = null; reject(new Error("Couldn't load the payment window. Check your connection.")); };
    document.body.appendChild(script);
  });
  return checkoutPromise;
}

export function useTipConfig() {
  const [config, setConfig] = useState(null);
  useEffect(() => { fetchTipConfig().then(setConfig).catch(() => setConfig({ enabled: false })); }, []);
  return config;
}

// "Tip" on a post: only when tipping is switched on and it isn't your own post.
export function TipButton({ post, variant = 'post' }) {
  const { currentUser } = useApp();
  const config = useTipConfig();
  const [open, setOpen] = useState(false);
  if (!config?.enabled || post.authorId === currentUser?.id) return null;
  return <>
    <button className={variant === 'reel' ? '' : 'tip-button'} onClick={() => setOpen(true)} aria-label={`Tip ${post.name}`}>
      <HandCoins/>{variant === 'reel' && <span>Tip</span>}
    </button>
    {open && createPortal(<TipSheet post={post} config={config} onClose={() => setOpen(false)}/>, document.body)}
  </>;
}

function TipSheet({ post, config, onClose }) {
  const { currentUser, showToast } = useApp();
  const [amount, setAmount] = useState(config.presets[1] || 50);
  const [custom, setCustom] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const rupees = custom ? Number(custom) : amount;
  const valid = Number.isInteger(rupees) && rupees >= config.min && rupees <= config.max;

  const pay = async () => {
    if (!valid || busy) return;
    setBusy(true);
    setError('');
    try {
      const [Razorpay, order] = await Promise.all([loadCheckout(), createTip({ creator: post.name, amount: rupees, postId: post.id, message: message.trim() })]);
      const checkout = new Razorpay({
        key: order.key_id,
        order_id: order.order_id,
        amount: order.amount_paise,
        currency: order.currency,
        name: 'Infogram',
        description: `Tip for ${order.creator}`,
        prefill: { email: currentUser?.email || '' },
        theme: { color: '#7c3aed' },
        handler: async (payment) => {
          try {
            await verifyTip(payment);
            showToast(`₹${rupees} sent to ${post.name}. Thank you for supporting useful content!`);
            onClose();
          } catch (verifyError) { setError(verifyError.message); setBusy(false); }
        },
        modal: { ondismiss: () => setBusy(false) },
      });
      checkout.on('payment.failed', (event) => { setError(event.error?.description || 'Payment failed.'); setBusy(false); });
      checkout.open();
    } catch (requestError) {
      setError(requestError.message);
      setBusy(false);
    }
  };

  return <div className="modal-backdrop menu-backdrop" onClick={() => !busy && onClose()}><section className="tip-sheet" onClick={(event) => event.stopPropagation()} role="dialog" aria-label={`Tip ${post.name}`}>
    <header><img src={post.avatar} alt=""/><div><b>Tip {post.name}</b><small>Did this post solve a problem for you? Say thanks.</small></div><button onClick={onClose} aria-label="Close tip" disabled={busy}><X/></button></header>
    <div className="tip-amounts" role="radiogroup" aria-label="Amount">
      {config.presets.map((value) => <button key={value} role="radio" aria-checked={!custom && amount === value} className={!custom && amount === value ? 'active' : ''} onClick={() => { setAmount(value); setCustom(''); }}>₹{value}</button>)}
    </div>
    <label className="tip-custom">Other amount<span>₹<input value={custom} onChange={(event) => setCustom(event.target.value.replace(/\D/g, '').slice(0, 5))} inputMode="numeric" placeholder={`${config.min}–${config.max}`}/></span></label>
    <textarea value={message} onChange={(event) => setMessage(event.target.value)} maxLength="200" rows="2" placeholder="Add a note (optional)"/>
    {error && <p className="auth-error" role="alert">{error}</p>}
    <button className="tip-pay" onClick={pay} disabled={!valid || busy}>{busy ? 'Opening payment…' : valid ? `Send ₹${rupees}` : `Enter ₹${config.min}–₹${config.max}`}</button>
    <p className="tip-note">Payments are processed securely by Razorpay (UPI, cards, netbanking).</p>
  </section></div>;
}

// Tips you received and sent, with totals.
export function TipsModal({ onClose }) {
  const [tab, setTab] = useState('received');
  const [data, setData] = useState(null);
  useEffect(() => { setData(null); fetchTips(tab).then(setData).catch(() => setData({ total: 0, count: 0, results: [] })); }, [tab]);
  return <div className="modal-backdrop new-message-backdrop" onClick={onClose}><section className="new-message-sheet tips-modal" onClick={(event) => event.stopPropagation()}>
    <header><b>Tips</b><button onClick={onClose} aria-label="Close"><X/></button></header>
    <div className="tips-tabs">{['received', 'sent'].map((name) => <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name === 'received' ? 'Received' : 'Sent'}</button>)}</div>
    {data === null ? <ListSkeleton rows={3}/> : <>
      <div className="tips-total"><span>₹{data.total.toLocaleString('en-IN')}</span><small>{data.count} {data.count === 1 ? 'tip' : 'tips'} {tab}</small></div>
      <div className="tips-list">
        {data.results.map((tip) => <div className="tip-row" key={tip.id}>
          <img src={avatarOf(tip.person || {})} alt=""/>
          <span><b>{tip.person?.username || 'Deleted account'}</b>{tip.message && <small>“{tip.message}”</small>}<small>{relativeTime(tip.created_at)}</small></span>
          <em>₹{tip.amount}</em>
        </div>)}
        {!data.results.length && <p className="new-message-status">{tab === 'received' ? 'When people tip your posts, it shows up here.' : "Tips you send to creators show up here."}</p>}
      </div>
      {tab === 'received' && data.count > 0 && <p className="tip-note">Payouts to your bank account are handled by the Infogram team for now.</p>}
    </>}
  </section></div>;
}
