import { type FormEvent, useState } from 'react'
import { Alert, Button, PageHeader, cardClass, inputClass } from '../components/ui'
import { useAuth } from '../hooks/useAuth'

export function ProfilePage() {
  const { user, changePassword, error, config } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [ok, setOk] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setOk(null)
    try {
      await changePassword(current, next)
      setCurrent('')
      setNext('')
      setOk('Your password was updated.')
    } catch {
      /* error on hook */
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-lg">
      <PageHeader
        title="Your account"
        subtitle={`${user?.person?.name ?? user?.username ?? ''}${user?.person?.employee_id ? ` · ${user.person.employee_id}` : ''}${config?.org_name || user?.org_name ? ` · ${config?.org_name || user?.org_name}` : ''}${config?.org_slug || user?.org_slug ? ` (${config?.org_slug || user?.org_slug})` : ''}${config?.default_site?.name ? ` · ${config.default_site.name}` : ''}`}
      />
      <form onSubmit={(e) => void onSubmit(e)} className={`${cardClass} space-y-3 p-6`}>
        <h2 className="text-sm font-semibold text-ink">Change password</h2>
        <input
          type="password"
          className={inputClass}
          placeholder="Current password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
        />
        <input
          type="password"
          className={inputClass}
          placeholder="New password (at least 8 characters)"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          required
          minLength={8}
        />
        {error ? <Alert kind="error">{error}</Alert> : null}
        {ok ? <Alert kind="ok">{ok}</Alert> : null}
        <Button type="submit" disabled={busy}>
          Update password
        </Button>
      </form>
    </div>
  )
}
