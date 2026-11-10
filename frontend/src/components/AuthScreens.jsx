import React, { useState } from 'react';
import { confirmPasswordReset, login, register, requestPasswordReset, verifyTwoFactor } from '../api';

export function AuthScreen({ onSuccess }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [challenge, setChallenge] = useState(null);
  const [code, setCode] = useState('');
  const switchMode = (next) => { setMode(next); setError(''); setNotice(''); setChallenge(null); setCode(''); };

  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      if (mode === 'forgot') {
        setNotice((await requestPasswordReset(email.trim())).detail);
        return;
      }
      if (challenge) {
        await verifyTwoFactor(challenge, code);
        onSuccess();
        return;
      }
      if (mode === 'register') await register({ username: username.trim(), email: email.trim(), password });
      const result = await login(username.trim(), password);
      if (result.twoFactor) { setChallenge(result.twoFactor.challenge); return; }
      onSuccess();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  return <main className="auth-shell"><section className="auth-card">
    <div className="auth-brand">Infogram</div>
    <p className="auth-tagline">Learn something useful in every scroll.</p>
    {mode === 'forgot'
      ? <p className="auth-forgot-title"><b>Trouble logging in?</b><br/>Enter your email and we'll send you a link to get back into your account.</p>
      : <div className="auth-tabs">
        <button className={mode === 'login' ? 'active-auth-tab' : ''} onClick={() => switchMode('login')}>Log in</button>
        <button className={mode === 'register' ? 'active-auth-tab' : ''} onClick={() => switchMode('register')}>Create account</button>
      </div>}
    {challenge ? <form className="auth-form" onSubmit={submit}>
      <p className="auth-forgot-title"><b>Two-step login</b><br/>Enter the 6-digit code from your authenticator app, or one of your recovery codes.</p>
      <input value={code} onChange={(event) => setCode(event.target.value)} placeholder="123 456" inputMode="numeric" autoComplete="one-time-code" autoFocus required aria-label="Authentication code" className="otp-input"/>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <button className="auth-submit" disabled={busy || code.trim().length < 6}>{busy ? 'Checking…' : 'Confirm'}</button>
      <button type="button" className="auth-link" onClick={() => switchMode('login')}>Back to log in</button>
    </form> : <form className="auth-form" onSubmit={submit}>
      {mode !== 'forgot' && <input value={username} onChange={(event) => setUsername(event.target.value)} placeholder={mode === 'login' ? 'Username or email' : 'Username'} autoComplete="username" required />}
      {mode !== 'login' && <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" type="email" autoComplete="email" required />}
      {mode !== 'forgot' && <input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password (8+ characters)" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength="8" required />}
      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="auth-notice" role="status">{notice}</p>}
      <button className="auth-submit" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Log in' : mode === 'register' ? 'Create account' : 'Send reset link'}</button>
    </form>}
    {mode === 'login' && !challenge && <button className="auth-link" onClick={() => switchMode('forgot')}>Forgot password?</button>}
    {mode === 'forgot' && <button className="auth-link" onClick={() => switchMode('login')}>Back to log in</button>}
  </section></main>;
}

// Opened from the emailed link: /reset-password?uid=...&token=...
export function ResetPasswordScreen({ uid, token, onDone }) {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    if (password !== confirm) { setError("Passwords don't match."); return; }
    setBusy(true);
    setError('');
    try { await confirmPasswordReset(uid, token, password); setDone(true); } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  };
  return <main className="auth-shell"><section className="auth-card">
    <div className="auth-brand">Infogram</div>
    {done
      ? <><p className="auth-notice" role="status">Password updated. You've been signed out on other devices.</p><button className="auth-submit" onClick={onDone}>Log in</button></>
      : <form className="auth-form" onSubmit={submit}>
        <p className="auth-forgot-title"><b>Create a new password</b><br/>At least 8 characters, not too common.</p>
        <input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="New password" type="password" autoComplete="new-password" minLength="8" required />
        <input value={confirm} onChange={(event) => setConfirm(event.target.value)} placeholder="Confirm new password" type="password" autoComplete="new-password" minLength="8" required />
        {error && <p className="auth-error" role="alert">{error}</p>}
        <button className="auth-submit" disabled={busy}>{busy ? 'Please wait…' : 'Reset password'}</button>
        <button type="button" className="auth-link" onClick={onDone}>Back to log in</button>
      </form>}
  </section></main>;
}
