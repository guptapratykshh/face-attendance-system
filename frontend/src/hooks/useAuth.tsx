import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import { ApiError, isPlatformAdmin, type AuthConfig, type User } from '../api/types'

type AuthState = {
  user: User | null
  loading: boolean
  error: string | null
  config: AuthConfig | null
  currentOrgId: number | null
  login: (username: string, password: string, org?: string) => Promise<void>
  register: (body: {
    username: string
    password: string
    name: string
    employee_id?: string
    org?: string
  }) => Promise<void>
  changePassword: (current: string, next: string) => Promise<void>
  refresh: () => Promise<void>
  refreshConfig: () => Promise<void>
  enterOrg: (orgId: number) => Promise<void>
  leaveOrg: () => void
  logout: () => void
}

function storageGet(key: string): string | null {
  try {
    return globalThis.localStorage?.getItem(key) ?? null
  } catch {
    return null
  }
}

function storageSet(key: string, value: string) {
  try {
    globalThis.localStorage?.setItem(key, value)
  } catch {
    /* ignore */
  }
}

function storageRemove(key: string) {
  try {
    globalThis.localStorage?.removeItem(key)
  } catch {
    /* ignore */
  }
}

const AuthContext = createContext<AuthState | null>(null)

function readStoredOrgId(): number | null {
  const raw = storageGet('frs_org_id')
  if (!raw) return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [config, setConfig] = useState<AuthConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentOrgId, setCurrentOrgId] = useState<number | null>(readStoredOrgId)

  const refreshConfig = useCallback(async () => {
    try {
      setConfig(await api.authConfig())
    } catch {
      /* public config may fail before the API is up */
    }
  }, [])

  const applyUser = useCallback((next: User) => {
    setUser(next)
    if (isPlatformAdmin(next)) {
      storageSet('frs_is_platform', '1')
    } else {
      storageRemove('frs_is_platform')
    }
    if (next.org_id != null) {
      storageSet('frs_org_id', String(next.org_id))
      setCurrentOrgId(next.org_id)
    } else if (isPlatformAdmin(next)) {
      /* keep stored org if they already opened one */
    }
  }, [])

  useEffect(() => {
    void refreshConfig()
    const token = storageGet('frs_token')
    if (!token) {
      setLoading(false)
      return
    }
    api
      .me()
      .then(applyUser)
      .catch(() => {
        storageRemove('frs_token')
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [refreshConfig, applyUser])

  const login = useCallback(async (username: string, password: string, org?: string) => {
    setError(null)
    try {
      const token = await api.login(username, password, org)
      storageSet('frs_token', token.access_token)
      const me = await api.me()
      if (isPlatformAdmin(me)) {
        storageRemove('frs_org_id')
        setCurrentOrgId(null)
        storageSet('frs_is_platform', '1')
      }
      applyUser(me)
      await refreshConfig()
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'login failed'
      setError(msg)
      throw err
    }
  }, [applyUser, refreshConfig])

  const register = useCallback(async (body: {
    username: string
    password: string
    name: string
    employee_id?: string
    org?: string
  }) => {
    setError(null)
    await api.register(body)
    await login(body.username, body.password, body.org)
  }, [login])

  const logout = useCallback(() => {
    storageRemove('frs_token')
    storageRemove('frs_org_id')
    storageRemove('frs_is_platform')
    setCurrentOrgId(null)
    setUser(null)
  }, [])

  const enterOrg = useCallback(async (orgId: number) => {
    storageSet('frs_org_id', String(orgId))
    setCurrentOrgId(orgId)
    await refreshConfig()
  }, [refreshConfig])

  const leaveOrg = useCallback(() => {
    storageRemove('frs_org_id')
    setCurrentOrgId(null)
  }, [])

  const refresh = useCallback(async () => {
    applyUser(await api.me())
  }, [applyUser])

  const changePassword = useCallback(async (current: string, next: string) => {
    setError(null)
    applyUser(await api.changePassword(current, next))
  }, [applyUser])

  const value = useMemo(
    () => ({
      user,
      loading,
      error,
      config,
      currentOrgId,
      login,
      register,
      changePassword,
      refresh,
      refreshConfig,
      enterOrg,
      leaveOrg,
      logout,
    }),
    [
      user,
      loading,
      error,
      config,
      currentOrgId,
      login,
      register,
      changePassword,
      refresh,
      refreshConfig,
      enterOrg,
      leaveOrg,
      logout,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
