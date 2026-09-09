import { type FormEvent, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { StaffUser } from '../api/types'
import { Alert, Button, EmptyState, PageHeader, StatusBadge, TableSkeleton, cardClass, inputClass } from '../components/ui'
import { useToast } from '../hooks/useToast'

export function StaffPage() {
  const toast = useToast()
  const [users, setUsers] = useState<StaffUser[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ username: '', password: '', role: 'hr' })
  const [resetId, setResetId] = useState<number | null>(null)
  const [newPassword, setNewPassword] = useState('')

  async function refresh() {
    setUsers(await api.listUsers())
  }

  useEffect(() => {
    refresh()
      .catch((e) => setError(e.detail ?? String(e)))
      .finally(() => setLoading(false))
  }, [])

  async function create(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await api.createUser(form)
      setForm({ username: '', password: '', role: 'hr' })
      toast.push('ok', 'Staff account created')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create user')
    }
  }

  async function changeRole(user: StaffUser, role: string) {
    try {
      await api.updateUser(user.id, { role })
      toast.push('ok', `${user.username} is now ${role}`)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update role')
    }
  }

  async function resetPassword(e: FormEvent) {
    e.preventDefault()
    if (resetId == null) return
    try {
      await api.updateUser(resetId, { password: newPassword })
      toast.push('ok', 'Password updated')
      setResetId(null)
      setNewPassword('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reset password')
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Access"
        title="Staff accounts"
        subtitle="Create HR, operator, or admin logins. Employee logins are still set from People."
      />
      {error ? <div className="mb-4"><Alert kind="error">{error}</Alert></div> : null}
      <form onSubmit={(e) => void create(e)} className={`${cardClass} grid gap-3 p-5 md:grid-cols-4`}>
        <input className={inputClass} placeholder="Username" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} required minLength={3} />
        <input type="password" className={inputClass} placeholder="Password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} required minLength={8} />
        <select className={inputClass} value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
          <option value="hr">HR</option>
          <option value="operator">Operator</option>
          <option value="admin">Admin</option>
        </select>
        <Button type="submit">Create</Button>
      </form>

      {resetId != null ? (
        <form onSubmit={(e) => void resetPassword(e)} className={`mt-4 ${cardClass} grid gap-3 p-5 md:grid-cols-2`}>
          <input type="password" className={inputClass} placeholder="New password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={8} />
          <div className="flex gap-2">
            <Button type="submit">Save password</Button>
            <Button type="button" variant="ghost" onClick={() => setResetId(null)}>Cancel</Button>
          </div>
        </form>
      ) : null}

      {loading ? (
        <div className="mt-5"><TableSkeleton /></div>
      ) : (
        <div className="mt-5 table-wrap">
          <table>
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="font-medium">{u.username}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={u.role} />
                      <select className="rounded-lg border border-line bg-panel px-2 py-1 text-xs" value={u.role} onChange={(e) => void changeRole(u, e.target.value)}>
                        <option value="admin">admin</option>
                        <option value="hr">hr</option>
                        <option value="operator">operator</option>
                        <option value="employee">employee</option>
                      </select>
                    </div>
                  </td>
                  <td className="mono text-muted">{new Date(u.created_at).toLocaleDateString()}</td>
                  <td>
                    <button type="button" className="text-sm font-medium hover:underline" onClick={() => setResetId(u.id)}>
                      Reset password
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 ? <EmptyState title="No staff yet" body="Create an HR or operator account above." /> : null}
        </div>
      )}
    </div>
  )
}
