import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type Theme = 'light' | 'dark'

const THEME_KEY = 'frs_theme_v3'

function readTheme(): Theme {
  try {
    const stored = globalThis.localStorage?.getItem(THEME_KEY)
    if (stored === 'dark') return 'dark'
    if (stored === 'light') return 'light'
    // Drop older keys so the product default stays light for first visit / after upgrade.
    globalThis.localStorage?.removeItem('frs_theme')
    globalThis.localStorage?.removeItem('frs_theme_v2')
  } catch {
    /* jsdom */
  }
  return 'light'
}

function applyTheme(theme: Theme) {
  const root = document.documentElement
  root.classList.toggle('dark', theme === 'dark')
  root.style.colorScheme = theme
}

type ThemeState = {
  theme: Theme
  toggle: () => void
  setTheme: (theme: Theme) => void
}

const ThemeContext = createContext<ThemeState | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => readTheme())

  useEffect(() => {
    applyTheme(theme)
    try {
      globalThis.localStorage?.setItem(THEME_KEY, theme)
    } catch {
      /* ignore */
    }
  }, [theme])

  const setTheme = useCallback((next: Theme) => setThemeState(next), [])
  const toggle = useCallback(() => setThemeState((t) => (t === 'dark' ? 'light' : 'dark')), [])
  const value = useMemo(() => ({ theme, toggle, setTheme }), [theme, toggle, setTheme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
