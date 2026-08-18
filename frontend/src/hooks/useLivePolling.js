import { useEffect, useRef } from 'react'

/**
 * Runs `callback` immediately, then again every `intervalMs` for as
 * long as the component is mounted and `deps` don't change identity.
 * Used to keep Findings, Audit Trail, and Logs feeling live rather
 * than requiring a manual refresh or tab switch to see new data.
 */
export function useLivePolling(callback, intervalMs, deps) {
  const savedCallback = useRef(callback)
  savedCallback.current = callback

  useEffect(() => {
    let cancelled = false
    const tick = () => { if (!cancelled) savedCallback.current() }
    tick()
    const id = setInterval(tick, intervalMs)
    return () => { cancelled = true; clearInterval(id) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}
