import { useEffect, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function SettingsPage({ agentCount }) {
  const [health, setHealth] = useState('checking')

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((r) => (r.ok ? setHealth('ok') : setHealth('error')))
      .catch(() => setHealth('error'))
  }, [])

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Settings</div>
        <div className="page-subtitle">
          Connection and environment information for this console.
        </div>
      </div>

      <div className="card">
        <h3 className="card-title">Backend connection</h3>
        <div className="kv-row">
          <span className="kv-label">API base URL</span>
          <span className="kv-value">{API_URL}</span>
        </div>
        <div className="kv-row">
          <span className="kv-label">Connection status</span>
          <span className="kv-value">
            {health === 'checking' && 'Checking…'}
            {health === 'ok' && <span style={{ color: 'var(--verified-600)' }}>Connected</span>}
            {health === 'error' && <span style={{ color: 'var(--critical-600)' }}>Unreachable</span>}
          </span>
        </div>
        <p className="helper-text">
          To point this console at a different backend, set <code>VITE_API_URL</code> in
          the frontend's <code>.env</code> file and rebuild (see the README's Deployment section).
        </p>
      </div>

      <div className="card">
        <h3 className="card-title">System</h3>
        <div className="kv-row">
          <span className="kv-label">Agents monitored</span>
          <span className="kv-value">{agentCount}</span>
        </div>
        <div className="kv-row">
          <span className="kv-label">Interactive API docs</span>
          <span className="kv-value">
            <a href={`${API_URL}/docs`} target="_blank" rel="noreferrer" style={{ color: 'var(--info-600)' }}>
              {API_URL}/docs
            </a>
          </span>
        </div>
      </div>

      <div className="card">
        <h3 className="card-title">Data</h3>
        <p className="helper-text" style={{ marginBottom: 0 }}>
          Deleting an agent (via the sidebar) permanently removes its profile,
          execution history, findings, responses, and audit entries. This action
          cannot be undone — there is no separate archive or trash.
        </p>
      </div>
    </div>
  )
}
