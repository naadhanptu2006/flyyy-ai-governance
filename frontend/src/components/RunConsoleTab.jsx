import { useState, useRef, useEffect } from 'react'
import { api } from '../api/client'
import { Stamp } from './Stamp'

const MAX_LIVE_STEPS = 40

export function RunConsoleTab({ agent, profile, onRunComplete }) {
  const [running, setRunning] = useState(false)
  const [trace, setTrace] = useState(null)
  const [runStatus, setRunStatus] = useState(null)

  const [liveActive, setLiveActive] = useState(false)
  const [liveRunId, setLiveRunId] = useState(null)
  const [liveSteps, setLiveSteps] = useState([])
  const [liveStats, setLiveStats] = useState({ executed: 0, blocked: 0 })
  const intervalRef = useRef(null)

  useEffect(() => () => clearInterval(intervalRef.current), [])

  const trigger = async (scenario) => {
    if (!profile) return
    setRunning(true)
    setTrace(null)
    try {
      const result = await api.runScenario(agent.id, scenario)
      setTrace(result.trace)
      setRunStatus(result.status)
      onRunComplete()
    } finally {
      setRunning(false)
    }
  }

  const startLive = async () => {
    if (!profile) return
    const { run_id } = await api.startLiveSession(agent.id)
    setLiveRunId(run_id)
    setLiveSteps([])
    setLiveStats({ executed: 0, blocked: 0 })
    setLiveActive(true)

    intervalRef.current = setInterval(async () => {
      try {
        const result = await api.liveTick(run_id)
        if (result.step) {
          setLiveSteps((prev) => [result.step, ...prev].slice(0, MAX_LIVE_STEPS))
          setLiveStats((prev) => ({
            executed: prev.executed + (result.step.result === 'executed' ? 1 : 0),
            blocked: prev.blocked + (result.step.result === 'BLOCKED' ? 1 : 0),
          }))
          onRunComplete()
        }
      } catch {
        clearInterval(intervalRef.current)
        setLiveActive(false)
      }
    }, 2200)
  }

  const stopLive = async () => {
    clearInterval(intervalRef.current)
    setLiveActive(false)
    if (liveRunId) await api.stopLiveSession(liveRunId)
    onRunComplete()
  }

  return (
    <div>
      <div className="card">
        <h3 className="card-title">Run Console</h3>
        {!profile && (
          <p className="helper-text">Create an approved behaviour profile in the Profile tab before running this agent.</p>
        )}
        {profile && (
          <>
            <p className="helper-text" style={{ marginBottom: 14 }}>
              Trigger a scripted execution, or switch on live monitoring to see the
              governance engine evaluate real, continuous activity as it happens.
            </p>
            <div className="btn-row">
              <button className="btn btn-primary" disabled={running || liveActive} onClick={() => trigger('normal')}>
                {running ? 'Running…' : 'Run: Normal behaviour'}
              </button>
              <button className="btn btn-danger" disabled={running || liveActive} onClick={() => trigger('deviation')}>
                {running ? 'Running…' : 'Run: Induce deviation'}
              </button>
              {!liveActive ? (
                <button className="btn" disabled={running} onClick={startLive}>
                  Start live monitor
                </button>
              ) : (
                <button className="btn btn-danger" onClick={stopLive}>
                  Stop live monitor
                </button>
              )}
            </div>
          </>
        )}
      </div>

      {liveActive && (
        <div className="card">
          <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
            <span>Live Monitor</span>
            <span className="live-indicator" style={{ marginBottom: 0 }}>
              <span className="live-dot" /> streaming every ~2s
            </span>
          </h3>
          <p className="helper-text" style={{ marginBottom: 12 }}>
            Each tick is one real, independently-evaluated action through the governance
            engine — a mix of normal in-profile activity and occasional out-of-scope
            probes, so you can watch detection and enforcement happen continuously
            rather than in one scripted batch. Findings, responses, and the audit trail
            update live in their own tabs as this runs.
          </p>
          <div style={{ display: 'flex', gap: 20, marginBottom: 14, fontFamily: 'var(--font-mono)', fontSize: 12.5 }}>
            <span style={{ color: 'var(--verified-600)' }}>{liveStats.executed} executed</span>
            <span style={{ color: 'var(--critical-600)' }}>{liveStats.blocked} blocked</span>
          </div>
          {liveSteps.length === 0 && <p className="helper-text">Waiting for the first tick…</p>}
          {liveSteps.map((step, i) => (
            <div className="trace-step" key={i}>
              <span style={{ color: 'var(--text-600)', minWidth: 18 }}>{liveSteps.length - i}</span>
              <span style={{ flex: 1 }}>{step.step}</span>
              <Stamp kind={step.result === 'executed' ? 'executed' : 'blocked'}>{step.result}</Stamp>
            </div>
          ))}
        </div>
      )}

      {!liveActive && trace && (
        <div className="card">
          <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
            <span>Execution Trace</span>
            {runStatus && <Stamp kind={runStatus === 'completed' ? 'executed' : runStatus === 'blocked' ? 'blocked' : 'pending'}>{runStatus.replace(/_/g, ' ')}</Stamp>}
          </h3>
          {trace.map((step, i) => (
            <div className="trace-step" key={i}>
              <span style={{ color: 'var(--text-600)', minWidth: 18 }}>{i + 1}</span>
              <span style={{ flex: 1 }}>{step.step}</span>
              <Stamp kind={step.result === 'executed' ? 'executed' : 'blocked'}>
                {step.result}
              </Stamp>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
