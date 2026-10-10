// Real-time telemetry readout (SPEC.md 3.3 directory listing). Camera
// tracking (ticket 02, OpticalColorTracker) and the BLE Touch Signal
// (ticket 05, BleTouchProvider) aren't built yet, so `camera` and `touch`
// are accepted as whatever placeholder/not-yet-wired shape their eventual
// producers choose -- this component only renders `status` (and `touch`'s
// optional live `isTouching` flag, which is already available today from
// the existing TRACK_UPDATE stream's `is_touching` field via App.jsx).
import { Camera, CameraOff, Hand, Wifi, WifiOff } from 'lucide-react'

const FIELD_CLASS =
  'flex items-center gap-1.5 rounded-full border border-chrome-border bg-chrome-bg px-3 py-1.5 text-xs font-medium text-chrome-muted backdrop-blur-md'
const OK_CLASS = 'text-ok'
const BAD_CLASS = 'text-danger'

export function StatusCapsule({ connectionState, camera, touch }) {
  const wsOk = connectionState === 'open'
  const cameraOk = camera.status === 'ok'
  const touchOk = touch.status === 'ok'

  return (
    <div className="pointer-events-none absolute top-4 left-4 z-10 flex gap-2">
      <span
        className={`${FIELD_CLASS} ${wsOk ? OK_CLASS : BAD_CLASS}`}
        data-field="ws"
        data-state={connectionState}
      >
        {wsOk ? <Wifi size={14} aria-hidden="true" /> : <WifiOff size={14} aria-hidden="true" />}
        WS: {connectionState}
      </span>
      <span
        className={`${FIELD_CLASS} ${cameraOk ? OK_CLASS : BAD_CLASS}`}
        data-field="camera"
        data-state={camera.status}
      >
        {cameraOk ? (
          <Camera size={14} aria-hidden="true" />
        ) : (
          <CameraOff size={14} aria-hidden="true" />
        )}
        Camera: {camera.status}
      </span>
      <span
        className={`${FIELD_CLASS} ${touchOk ? OK_CLASS : BAD_CLASS}`}
        data-field="touch"
        data-testid="status-touch"
        data-state={touch.status}
        data-touching={Boolean(touch.isTouching)}
      >
        <Hand size={14} aria-hidden="true" />
        Touch: {touch.status}
        {touchOk ? ` (${touch.isTouching ? 'touching' : 'up'})` : ''}
      </span>
    </div>
  )
}
