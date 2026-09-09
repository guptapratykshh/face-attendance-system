import { api } from '../api/client'
import type { LivenessResponse } from '../api/types'

function isoDay(d: Date) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function datePreset(kind: 'today' | 'week' | 'month') {
  const now = new Date()
  const to = isoDay(now)
  if (kind === 'today') return { from: to, to }
  if (kind === 'week') {
    const start = new Date(now)
    const day = (start.getDay() + 6) % 7
    start.setDate(start.getDate() - day)
    return { from: isoDay(start), to }
  }
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  return { from: isoDay(start), to }
}

export async function downloadAuthCsv(url: string, filename: string) {
  const token = localStorage.getItem('frs_token')
  if (!token) return
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  const blob = await res.blob()
  const href = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  a.click()
  URL.revokeObjectURL(href)
}

export function fenceOn(
  office: {
    geo_lat?: number | null
    geo_lng?: number | null
    geo_radius_m?: number | null
    geofence_on_self_punch?: boolean
  } | null | undefined,
) {
  if (office?.geofence_on_self_punch === false) return false
  return office?.geo_lat != null && office?.geo_lng != null && Number(office.geo_radius_m) > 0
}

export function readCoords(required = false): Promise<{ lat: number; lng: number } | undefined> {
  if (!navigator.geolocation) {
    if (required) return Promise.reject(new Error('This browser cannot share location. Check in at the office kiosk.'))
    return Promise.resolve(undefined)
  }
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      (err) => {
        if (required) {
          reject(
            new Error(
              err.code === 1
                ? 'Allow location for this site. Attendance only counts at the office.'
                : 'Could not read your location. Stand outside, then try again.',
            ),
          )
          return
        }
        resolve(undefined)
      },
      { enableHighAccuracy: true, timeout: required ? 12000 : 4000, maximumAge: 15_000 },
    )
  })
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function checkBlinkChallenge(
  cam: { captureBurst: (n: number, intervalMs: number) => Promise<Blob[]> },
  onHint?: (message: string) => void,
  source = 'lab',
): Promise<{ challengeId: string; result: LivenessResponse }> {
  const challenge = await api.issueChallenge()
  const holdMs = challenge.hold_ms ?? 1200
  const holdN = challenge.hold_frames ?? 8
  const blinkN = challenge.blink_frames ?? 16
  const interval = challenge.interval_ms ?? 70
  onHint?.('Keep your eyes open…')
  await sleep(holdMs)
  const hold = await cam.captureBurst(holdN, interval)
  onHint?.('Blink once now…')
  const action = await cam.captureBurst(blinkN, interval)
  const result = await api.checkLiveness(challenge.challenge_id, [...hold, ...action], source)
  return { challengeId: challenge.challenge_id, result }
}

export async function runBlinkChallenge(
  cam: { captureBurst: (n: number, intervalMs: number) => Promise<Blob[]> },
  onHint?: (message: string) => void,
  source = 'attendance',
): Promise<string> {
  const { challengeId, result } = await checkBlinkChallenge(cam, onHint, source)
  if (!result.live) {
    const textureReason = typeof result.texture?.reason === 'string' ? result.texture.reason : ''
    if (
      textureReason.includes('frozen') ||
      textureReason.includes('recapture') ||
      textureReason.includes('screen')
    ) {
      throw new Error('That looked like a photo or a screen. Face the camera yourself and try again.')
    }
    throw new Error('We could not confirm a blink. Look at the camera, wait for the prompt, then blink once.')
  }
  return challengeId
}
