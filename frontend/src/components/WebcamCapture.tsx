import { useWebcam } from '../hooks/useWebcam'
import { ScanFrame } from './ScanFrame'
import { Button, cardClass } from './ui'

type Props = {
  onCapture: (file: File) => void
  overlay?: boolean
  tone?: 'idle' | 'ok' | 'bad'
  scanning?: boolean
}

export function WebcamCapture({ onCapture, overlay = false, tone = 'idle', scanning = true }: Props) {
  const cam = useWebcam()
  return (
    <div className={`${cardClass} overflow-hidden`}>
      <div className="relative">
        <video ref={cam.videoRef} className="w-full aspect-video bg-black object-cover" playsInline muted />
        {overlay && cam.ready ? <ScanFrame active={scanning} tone={tone} /> : null}
      </div>
      <div className="flex gap-2 p-4">
        {!cam.ready ? (
          <Button onClick={() => void cam.start()}>Start camera</Button>
        ) : (
          <>
            <Button
              onClick={async () => {
                const blob = await cam.capture()
                onCapture(new File([blob], 'webcam.jpg', { type: 'image/jpeg' }))
              }}
            >
              Take photo
            </Button>
            <Button variant="ghost" onClick={cam.stop}>
              Stop
            </Button>
          </>
        )}
      </div>
      {cam.error ? <p className="px-4 pb-4 text-sm text-rose-600 dark:text-rose-400">{cam.error}</p> : null}
    </div>
  )
}

export { useWebcam }
