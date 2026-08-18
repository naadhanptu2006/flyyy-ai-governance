import { useState } from 'react'
import { api } from '../api/client'
import { Stamp } from './Stamp'
import { useLivePolling } from '../hooks/useLivePolling'

export function FindingsTab({ agent, refreshKey }) {
  const [findings, setFindings] = useState([])
  const [responses, setResponses] = useState({}) // finding_id -> response
  const [approver, setApprover] = useState('reviewer@flyyy.ai')

  const load = async () => {
    const [f, r] = await Promise.all([api.listFindings(agent.id), api.listResponses()])
    setFindings(f)
    const map = {}
    r.forEach((resp) => { map[resp.finding_id] = resp })
    setResponses(map)
  }

  useLivePolling(load, 4000, [agent.id, refreshKey])

  const decide = async (responseId, approve) => {
    const reason = approve ? 'Reviewed and approved by governance team' : 'Rejected — outside policy'
    if (approve) await api.approveResponse(responseId, approver, reason)
    else await api.rejectResponse(responseId, approver, reason)
    load()
  }

  if (findings.length === 0) {
    return <div className="card"><div className="empty-state">No deviations recorded yet for this agent.</div></div>
  }

  return (
    <div>
      <div className="live-indicator"><span className="live-dot" /> Live — updates automatically</div>
      {findings.map((f) => {
        const response = responses[f.id]
        return (
          <div className="ledger-entry" key={f.id}>
            <div className="entry-top">
              <span className="entry-type">{f.deviation_type.replace(/_/g, ' ')}</span>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <Stamp kind={f.severity}>{f.severity}</Stamp>
                {response && <Stamp kind={response.status === 'approved' ? 'approved' : response.status === 'rejected' ? 'rejected' : response.action_type === 'block' ? 'blocked' : 'pending'}>
                  {response.status === 'pending' ? response.action_type.replace('_', ' ') : response.status}
                </Stamp>}
              </div>
            </div>
            <div className="entry-line"><b>Expected:</b> {f.expected_behavior}</div>
            <div className="entry-line"><b>Actual:</b> {f.actual_behavior}</div>
            <div className="entry-line entry-time">
              Run {f.run_id.slice(0, 8)} · detected {new Date(f.detected_at).toLocaleString()}
            </div>

            {response && response.status === 'pending' && response.action_type === 'require_approval' && (
              <div className="btn-row" style={{ marginTop: 10 }}>
                <button className="btn btn-primary" onClick={() => decide(response.id, true)}>Approve & resume</button>
                <button className="btn btn-danger" onClick={() => decide(response.id, false)}>Reject</button>
              </div>
            )}
            {response && response.action_type === 'block' && response.status === 'pending' && (
              <div className="helper-text" style={{ marginTop: 10, color: 'var(--critical-600)' }}>
                High severity — agent halted. No auto-resume; escalate manually if this was expected.
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
