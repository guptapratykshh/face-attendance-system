import { type FormEvent, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { api } from '../api/client'
import { homePath } from '../api/types'
import { Alert, Button, ThemeToggle, inputClass } from '../components/ui'
import { Logo } from '../components/Logo'
import { useAuth } from '../hooks/useAuth'

import { orgFrom } from '../lib/org'

export function LoginPage() {
  const { user, login, register, error, loading, config } = useAuth()
  const org = orgFrom(config)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [orgSlug, setOrgSlug] = useState('')
  const [name, setName] = useState('')
  const [employeeId, setEmployeeId] = useState('')
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [busy, setBusy] = useState(false)
  const [allowRegister, setAllowRegister] = useState(false)
  const [justRegistered, setJustRegistered] = useState(false)

  useEffect(() => {
    api
      .authConfig()
      .then((c) => setAllowRegister(c.allow_public_register))
      .catch(() => undefined)
  }, [])

  if (!loading && user && !justRegistered) {
    return <Navigate to={homePath(user)} replace />
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      if (mode === 'login') await login(username, password, orgSlug.trim() || undefined)
      else {
        await register({
          username,
          password,
          name: name.trim(),
          employee_id: employeeId.trim() || undefined,
          org: orgSlug.trim() || undefined,
        })
        setJustRegistered(true)
      }
    } catch {
      /* error is on the auth hook */
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="relative hidden overflow-hidden lg:flex flex-col justify-between bg-ink p-12 text-accent-fg">
        <div className="scan-hero pointer-events-none absolute inset-0 opacity-40" />
        <div className="scan-line pointer-events-none absolute inset-x-0 top-1/3 opacity-70" />
        <div className="relative z-10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Logo ghost wordmark={false} />
            <div>
              <div className="text-lg font-semibold leading-none">Sentinel</div>
              <div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-accent-fg/55">
                Org face attendance
              </div>
            </div>
          </div>
          <ThemeToggle inverted />
        </div>
        <div className="relative z-10">
          <h1 className="text-4xl font-semibold leading-tight">
            Your org. Your people.
            <br />
            Present for real.
          </h1>
          <p className="mt-4 max-w-md text-accent-fg/75 leading-7">
            Every organization gets its own space. Staff check in with a live face - not a shared PIN. HR sees who
            showed up, who is late, and who still needs a photo. One code. One team. Everyone accountable.
          </p>
        </div>
        <p className="relative z-10 text-sm text-accent-fg/60">
          Multi-organization attendance · face verification
        </p>
      </div>
      <div className="flex items-center justify-center p-6">
        {justRegistered ? (
          <div className="w-full max-w-md rounded-3xl border border-line bg-panel p-8 shadow-sm">
            <h2 className="text-2xl font-semibold text-ink">You are signed up</h2>
            <p className="mt-2 text-sm text-muted">Three steps before you can check in:</p>
            <ol className="mt-6 space-y-4">
              {[
                { n: '1', t: 'HR adds your photo', d: 'Someone from HR enrolls your face in Sentinel.' },
                { n: '2', t: 'You wait for the green light', d: 'The check-in page updates by itself when you are ready.' },
                { n: '3', t: 'Look at the camera', d: 'Blink once if asked, then you are marked present.' },
              ].map((s) => (
                <li key={s.n} className="flex gap-3">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-soft text-sm font-semibold">{s.n}</span>
                  <div>
                    <div className="font-medium">{s.t}</div>
                    <p className="text-sm text-muted">{s.d}</p>
                  </div>
                </li>
              ))}
            </ol>
            <Button className="mt-8 w-full" onClick={() => setJustRegistered(false)}>
              Continue to check-in
            </Button>
          </div>
        ) : (
        <form onSubmit={(e) => void onSubmit(e)} className="w-full max-w-md rounded-3xl border border-line bg-panel p-8 shadow-sm">
          <div className="mb-6 flex items-center justify-between">
            <div className="lg:hidden flex items-center gap-2">
              <Logo compact wordmark={false} />
              <span className="font-semibold">Sentinel</span>
            </div>
            <ThemeToggle className="ml-auto lg:hidden" />
          </div>
          <h2 className="text-2xl font-semibold text-ink">
            {mode === 'login' ? 'Welcome back' : 'Create your account'}
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            {mode === 'login'
              ? `Use your organization code plus the username and password from ${org.staff}. Platform admin can leave the code blank.`
              : `Tell us your name and organization code. ${org.staff} will add your photo before you can check in.`}
          </p>
          {mode === 'register' ? (
            <>
              <label className="mt-6 block text-sm font-medium text-ink">Full name</label>
              <input className={`mt-1.5 ${inputClass}`} value={name} onChange={(e) => setName(e.target.value)} required />
              <label className="mt-4 block text-sm font-medium text-ink">{org.id} (optional)</label>
              <input
                className={`mt-1.5 ${inputClass}`}
                value={employeeId}
                onChange={(e) => setEmployeeId(e.target.value)}
              />
            </>
          ) : null}
          <label className={`${mode === 'register' ? 'mt-4' : 'mt-6'} block text-sm font-medium text-ink`}>
            Organization code
          </label>
          <input
            className={`mt-1.5 ${inputClass}`}
            value={orgSlug}
            onChange={(e) => setOrgSlug(e.target.value)}
            autoComplete="organization"
            placeholder="north-campus"
          />
          <p className="mt-1 text-xs text-muted">Leave blank if you are the platform admin.</p>
          <label className="mt-4 block text-sm font-medium text-ink">
            Username
          </label>
          <input
            className={`mt-1.5 ${inputClass}`}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
          <label className="mt-4 block text-sm font-medium text-ink">Password</label>
          <input
            type="password"
            className={`mt-1.5 ${inputClass}`}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            required
          />
          {error ? (
            <div className="mt-4">
              <Alert kind="error">{error}</Alert>
            </div>
          ) : null}
          <Button type="submit" disabled={busy} className="mt-6 w-full py-3">
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </Button>
          {allowRegister ? (
            <button
              type="button"
              className="mt-4 w-full text-sm text-muted hover:text-ink"
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login')
                setUsername('')
                setPassword('')
              }}
            >
              {mode === 'login' ? `New ${org.subject}? Create an account` : 'Already have an account? Sign in'}
            </button>
          ) : (
            <p className="mt-4 text-center text-xs text-muted">Need an account? Ask {org.staff} for a username.</p>
          )}
        </form>
        )}
      </div>
    </div>
  )
}
