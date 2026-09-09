import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

export const server = setupServer(
  http.post('/api/v1/auth/login', async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string }
    if (body.username === 'admin' && body.password === 'admin1234') {
      return HttpResponse.json({ access_token: 'test-token', token_type: 'bearer', username: 'admin' })
    }
    return HttpResponse.json({ detail: 'incorrect username or password' }, { status: 401 })
  }),
  http.get('/api/v1/auth/me', () =>
    HttpResponse.json({
      id: 1,
      username: 'admin',
      is_admin: true,
      role: 'admin',
      org_id: null,
      created_at: '2026-01-01T00:00:00Z',
      person: null,
    }),
  ),
  http.get('/api/v1/auth/config', () =>
    HttpResponse.json({
      allow_public_register: true,
      require_liveness: false,
      tz: 'Asia/Kolkata',
      allow_kiosk_pin: false,
      org_type: 'workplace',
      kernel: 'daily_inout',
      subject_label: 'employee',
      staff_label: 'HR',
      allow_checkout: true,
    }),
  ),
  http.get('/api/v1/health', () =>
    HttpResponse.json({
      status: 'ok',
      encoder: 'facenet',
      gallery_size: 0,
      verify_threshold: 0.5,
      identify_threshold: 0.5,
      device: 'cpu',
    }),
  ),
)
