import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { api } from '../api/client'
import { MetricCard } from '../components/MetricCard'
import { AuthProvider } from '../hooks/useAuth'
import { ThemeProvider } from '../hooks/useTheme'
import { LoginPage } from '../pages/Login'

describe('MetricCard', () => {
  it('renders label and value', () => {
    render(<MetricCard label="EER" value="2.43%" hint="lower is better" />)
    expect(screen.getByText('EER')).toBeInTheDocument()
    expect(screen.getByText('2.43%')).toBeInTheDocument()
  })
})

describe('api client', () => {
  it('logs in against the mocked API', async () => {
    const token = await api.login('admin', 'admin1234')
    expect(token.access_token).toBe('test-token')
    expect(token.username).toBe('admin')
  })

  it('maps 401 to ApiError', async () => {
    await expect(api.login('nope', 'nope')).rejects.toMatchObject({ status: 401 })
  })
})

describe('Login page', () => {
  it('renders the operator sign-in form', () => {
    render(
      <ThemeProvider>
        <MemoryRouter>
          <AuthProvider>
            <LoginPage />
          </AuthProvider>
        </MemoryRouter>
      </ThemeProvider>,
    )
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    expect(screen.getByText(/Platform admin can leave the code blank/i)).toBeInTheDocument()
  })
})
