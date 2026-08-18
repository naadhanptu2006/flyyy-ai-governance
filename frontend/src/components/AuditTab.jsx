import { useState } from 'react'
import { api } from '../api/client'
import { useLivePolling } from '../hooks/useLivePolling'

export function AuditTab({ agent, refreshKey }) {
  const [log, setLog] = useState([])
  const [guardrails, setGuardrails] = useState([])

  useLivePolling(() => {
    api.auditLog(agent.id).then(setLog)
    api.guardrailStatus(agent.id).then((r) => setGuardrails(r.warnings || []))
  }, 4000, [agent.id, refreshKey])

  return (
    <div>
      <div className="live-indicator"><span className="live-dot" /> Live — updates automatically</div>
      <div className="card">
        <h3 className="card-title">Guardrail Status</h3>
        {guardrails.length === 0 && <p className="helper-text">No guardrails currently in a warning zone.</p>}
        {guardrails.map((w) => (
          <div className="field-row" key={w.guardrail}>
            <span className="field-label">{w.guardrail.replace(/_/g, ' ')} — {w.usage}/{w.limit} ({w.pct}%)</span>
            <div className="guardrail-bar-track">
              <div
                className="guardrail-bar-fill"
                style={{
                  width: `${Math.min(w.pct, 100)}%`,
                  background: w.level === 'limit_exceeded' ? 'var(--critical-600)'
                    : w.level === 'critical' ? 'var(--warning-600)' : 'var(--info-600)',
                }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h3 className="card-title">Audit Trail</h3>
        {log.length === 0 && <div className="empty-state">No audit entries yet.</div>}
        {log.map((entry) => (
          <div className="ledger-entry" key={entry.id}>
            <div className="entry-top">
              <span className="entry-type">{entry.event_type.replace(/_/g, ' ')}</span>
              <span className="entry-time">{new Date(entry.timestamp).toLocaleString()}</span>
            </div>
            <div className="entry-line"><b>Actor:</b> {entry.actor}</div>
            {Object.entries(entry.details || {}).map(([k, v]) => (
              <div className="entry-line" key={k}><b>{k}:</b> {String(v)}</div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
