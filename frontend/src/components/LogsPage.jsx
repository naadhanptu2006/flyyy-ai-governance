import { useState } from 'react'
import { api } from '../api/client'
import { useLivePolling } from '../hooks/useLivePolling'

export function LogsPage({ agents }) {
  const [log, setLog] = useState([])
  const [filterAgentId, setFilterAgentId] = useState('all')
  const [loading, setLoading] = useState(true)

  useLivePolling(() => {
    const agentId = filterAgentId === 'all' ? undefined : filterAgentId
    api.auditLog(agentId).then((data) => { setLog(data); setLoading(false) })
  }, 4000, [filterAgentId])

  const agentName = (id) => agents.find((a) => a.id === id)?.name || id?.slice(0, 8) || '—'

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Audit Logs</div>
        <div className="page-subtitle">
          Every governance-relevant event across every monitored agent — deviations,
          responses, approvals, and guardrail warnings.
        </div>
        <div className="live-indicator" style={{ marginTop: 10 }}><span className="live-dot" /> Live — updates automatically</div>
      </div>

      <div className="agent-filter-row">
        <button
          className={`pill-option ${filterAgentId === 'all' ? 'active' : ''}`}
          onClick={() => setFilterAgentId('all')}
        >
          All agents
        </button>
        {agents.map((a) => (
          <button
            key={a.id}
            className={`pill-option ${filterAgentId === a.id ? 'active' : ''}`}
            onClick={() => setFilterAgentId(a.id)}
          >
            {a.name}
          </button>
        ))}
      </div>

      {loading && <div className="empty-state">Loading…</div>}
      {!loading && log.length === 0 && (
        <div className="card"><div className="empty-state">No audit entries recorded yet.</div></div>
      )}
      {!loading && log.map((entry) => (
        <div className="ledger-entry" key={entry.id}>
          <div className="entry-top">
            <div>
              <span className="entry-type">{entry.event_type.replace(/_/g, ' ')}</span>
            </div>
            <span className="entry-time">{new Date(entry.timestamp).toLocaleString()}</span>
          </div>
          <div className="entry-line"><b>Agent:</b> {agentName(entry.agent_id)}</div>
          <div className="entry-line"><b>Actor:</b> {entry.actor}</div>
          {Object.entries(entry.details || {}).map(([k, v]) => (
            <div className="entry-line" key={k}><b>{k}:</b> {String(v)}</div>
          ))}
        </div>
      ))}
    </div>
  )
}
