import { useCallback, useEffect, useRef, useState } from 'react'

function isAbort(err: unknown) {
  return err instanceof Error && (err.name === 'AbortError' || /interrupted by a new load request/i.test(err.message))
}

export function useWebcam() {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const startingRef = useRef<Promise<void> | null>(null)
  const genRef = useRef(0)

  const stop = useCallback(() => {
    genRef.current += 1
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    startingRef.current = null
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
    setReady(false)
  }, [])

  const start = useCallback(async () => {
    if (streamRef.current && videoRef.current) {
      if (videoRef.current.srcObject !== streamRef.current) {
        videoRef.current.srcObject = streamRef.current
      }
      try {
        await videoRef.current.play()
      } catch (err) {
        if (!isAbort(err)) {
          setError('Allow the camera, then try again.')
        }
      }
      setReady(true)
      return
    }
    if (startingRef.current) {
      await startingRef.current
      return
    }

    const gen = genRef.current
    const run = (async () => {
      setError(null)
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
          audio: false,
        })
        if (gen !== genRef.current) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        const video = videoRef.current
        if (!video) {
          stream.getTracks().forEach((t) => t.stop())
          streamRef.current = null
          return
        }
        video.muted = true
        video.playsInline = true
        video.srcObject = stream
        try {
          await video.play()
        } catch (err) {
          if (!isAbort(err)) throw err
        }
        if (gen !== genRef.current) return
        setReady(true)
      } catch (err) {
        if (isAbort(err) || gen !== genRef.current) return
        setError('Allow the camera, then try again.')
        setReady(false)
      } finally {
        if (gen === genRef.current) startingRef.current = null
      }
    })()
    startingRef.current = run
    await run
  }, [])

  const capture = useCallback(async (quality = 0.85): Promise<Blob> => {
    const video = videoRef.current
    if (!video) throw new Error('camera not ready')
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth || 640
    canvas.height = video.videoHeight || 480
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('canvas unavailable')
    ctx.drawImage(video, 0, 0)
    return await new Promise((resolve, reject) => {
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('capture failed'))), 'image/jpeg', quality)
    })
  }, [])

  const captureBurst = useCallback(async (n: number, intervalMs: number): Promise<Blob[]> => {
    const video = videoRef.current
    if (!video) throw new Error('camera not ready')
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth || 640
    canvas.height = video.videoHeight || 480
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('canvas unavailable')
    const snaps: ImageData[] = []
    for (let i = 0; i < n; i += 1) {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      snaps.push(ctx.getImageData(0, 0, canvas.width, canvas.height))
      if (i < n - 1) await new Promise((r) => setTimeout(r, intervalMs))
    }
    const frames: Blob[] = []
    for (const snap of snaps) {
      ctx.putImageData(snap, 0, 0)
      frames.push(
        await new Promise((resolve, reject) => {
          canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('capture failed'))), 'image/jpeg', 0.8)
        }),
      )
    }
    return frames
  }, [])

  useEffect(() => () => stop(), [stop])

  return { videoRef, ready, error, start, stop, capture, captureBurst }
}
