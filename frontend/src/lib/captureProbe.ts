/**
 * Capture-path integrity probe.
 *
 * Liveness checks read the *content* of the video. They cannot see that a virtual camera
 * (OBS, ManyCam, SplitCam) replaced the physical device, because an injected face-swap blinks on
 * cue. What a virtual camera cannot fake cheaply is how a real sensor *reacts to being
 * reconfigured*: real hardware negotiates resolution and frame rate with a driver, so it applies
 * some values and refuses others, with response times that vary by how standard the request is.
 * Software cameras usually accept everything instantly, or clamp hard at whatever the operator
 * configured.
 *
 * So we ask the track to change shape a few times and record what happens. The classifier lives
 * server-side in app/liveness/capture_path.py; this file only collects evidence.
 *
 * Method follows arXiv 2512.10653. Camera labels are deliberately not used as a signal - they are
 * routinely renamed or blanked by the attack tooling.
 */

export type ProbeStep = {
  /** Which knob was turned. */
  kind: 'height' | 'fps'
  /** What we asked for. */
  requested: number
  /** What the browser claims it gave us, via track.getSettings(). */
  reported: number | null
  /** What we actually observed on the <video> element. */
  actual: number | null
  /** How long applyConstraints took to settle, in milliseconds. */
  response_ms: number
  /** False when applyConstraints rejected outright. */
  applied: boolean
}

export type CaptureProbeReport = {
  schema: 1
  /** Milliseconds spent on the whole ladder. */
  duration_ms: number
  /** Settings the track reported before we touched anything. */
  baseline: { width: number | null; height: number | null; frame_rate: number | null }
  steps: ProbeStep[]
  /** Coarse environment context; useful for slicing results, not used as a spoof signal. */
  context: {
    user_agent: string
    platform: string | null
    device_count: number | null
    /** True when the browser exposes non-standard capture APIs we relied on. */
    has_video_frame_callback: boolean
  }
}

/** 3001 is deliberately out of range - real drivers clamp it, some virtual cameras accept it. */
const HEIGHT_LADDER = [240, 480, 720, 3001]
const FPS_LADDER = [1, 30, 120, 200]

const SETTLE_MS = 60
const FPS_WINDOW_MS = 220

type VideoFrameCallbackHost = HTMLVideoElement & {
  requestVideoFrameCallback?: (cb: () => void) => number
  cancelVideoFrameCallback?: (handle: number) => void
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Count frames the compositor actually delivers over a short window.
 *
 * requestVideoFrameCallback fires once per decoded frame, which is exactly what we want. Where it
 * is missing we fall back to sampling currentTime, which only tells us whether the stream advanced
 * at all - enough to catch a frozen feed, not enough to measure true rate.
 */
async function measureFps(video: HTMLVideoElement): Promise<number | null> {
  const host = video as VideoFrameCallbackHost
  const start = performance.now()

  if (typeof host.requestVideoFrameCallback === 'function') {
    let frames = 0
    let handle = 0
    let done = false
    const tick = () => {
      if (done) return
      frames += 1
      handle = host.requestVideoFrameCallback!(tick)
    }
    handle = host.requestVideoFrameCallback(tick)
    await sleep(FPS_WINDOW_MS)
    done = true
    host.cancelVideoFrameCallback?.(handle)
    const elapsed = performance.now() - start
    if (elapsed <= 0) return null
    return Number(((frames * 1000) / elapsed).toFixed(2))
  }

  const first = video.currentTime
  await sleep(FPS_WINDOW_MS)
  const advanced = video.currentTime - first
  if (advanced <= 0) return 0
  return null
}

async function probeStep(
  track: MediaStreamTrack,
  video: HTMLVideoElement,
  kind: ProbeStep['kind'],
  requested: number,
): Promise<ProbeStep> {
  const started = performance.now()
  let applied = true
  try {
    await track.applyConstraints(
      kind === 'height' ? { height: { ideal: requested } } : { frameRate: { ideal: requested } },
    )
  } catch {
    // A refusal is itself evidence, so record it rather than aborting the ladder.
    applied = false
  }
  const response_ms = Number((performance.now() - started).toFixed(2))
  await sleep(SETTLE_MS)

  const settings = track.getSettings()
  if (kind === 'height') {
    return {
      kind,
      requested,
      reported: settings.height ?? null,
      actual: video.videoHeight || null,
      response_ms,
      applied,
    }
  }
  return {
    kind,
    requested,
    reported: settings.frameRate != null ? Number(settings.frameRate.toFixed(2)) : null,
    actual: await measureFps(video),
    response_ms,
    applied,
  }
}

async function deviceCount(): Promise<number | null> {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    return devices.filter((d) => d.kind === 'videoinput').length
  } catch {
    return null
  }
}

/**
 * Run the constraint ladder and restore the track to how we found it.
 *
 * Must not overlap face capture: the probe deliberately changes resolution, so frames taken while
 * it runs would be the wrong shape.
 */
export async function runCaptureProbe(
  stream: MediaStream,
  video: HTMLVideoElement,
): Promise<CaptureProbeReport | null> {
  const track = stream.getVideoTracks()[0]
  if (!track || track.readyState !== 'live') return null

  const started = performance.now()
  const before = track.getSettings()
  const steps: ProbeStep[] = []

  try {
    for (const height of HEIGHT_LADDER) {
      steps.push(await probeStep(track, video, 'height', height))
    }
    for (const fps of FPS_LADDER) {
      steps.push(await probeStep(track, video, 'fps', fps))
    }
  } catch {
    // Partial ladders are still scoreable; the server treats missing steps as missing features.
  } finally {
    try {
      await track.applyConstraints({
        width: { ideal: before.width ?? 640 },
        height: { ideal: before.height ?? 480 },
        ...(before.frameRate ? { frameRate: { ideal: before.frameRate } } : {}),
      })
    } catch {
      /* the stream keeps whatever the last probe left it at */
    }
  }

  return {
    schema: 1,
    duration_ms: Number((performance.now() - started).toFixed(2)),
    baseline: {
      width: before.width ?? null,
      height: before.height ?? null,
      frame_rate: before.frameRate != null ? Number(before.frameRate.toFixed(2)) : null,
    },
    steps,
    context: {
      user_agent: navigator.userAgent,
      platform: navigator.platform || null,
      device_count: await deviceCount(),
      has_video_frame_callback:
        typeof (video as VideoFrameCallbackHost).requestVideoFrameCallback === 'function',
    },
  }
}
