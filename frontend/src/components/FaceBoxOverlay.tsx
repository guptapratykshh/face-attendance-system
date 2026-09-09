import { useEffect, useRef } from 'react'
import type { FaceInfo } from '../api/types'

type Props = {
  src: string
  face?: FaceInfo
}

export function FaceBoxOverlay({ src, face }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imgRef = useRef<HTMLImageElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const img = imgRef.current
    if (!canvas || !img) return
    const draw = () => {
      canvas.width = img.naturalWidth || img.width
      canvas.height = img.naturalHeight || img.height
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
      if (!face) return
      const [x1, y1, x2, y2] = face.bbox
      ctx.strokeStyle = '#14b8a6'
      ctx.lineWidth = 3
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
      ctx.fillStyle = '#14b8a6'
      for (const [x, y] of face.landmarks) {
        ctx.beginPath()
        ctx.arc(x, y, 3, 0, Math.PI * 2)
        ctx.fill()
      }
    }
    if (img.complete) draw()
    else img.onload = draw
  }, [src, face])

  return (
    <div className="relative overflow-hidden rounded-2xl border border-line bg-panel">
      <img ref={imgRef} src={src} alt="" className="hidden" />
      <canvas ref={canvasRef} className="w-full h-auto block" />
    </div>
  )
}
