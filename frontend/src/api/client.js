const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  listAgents: () => request('/agents'),
  createAgent: (data) => request('/agents', { method: 'POST', body: JSON.stringify(data) }),
  deleteAgent: (id) => request(`/agents/${id}`, { method: 'DELETE' }),
  activateProfile: (agentId, profileId) =>
    request(`/agents/${agentId}/activate-profile/${profileId}`, { method: 'POST' }),

  listProfiles: (agentId) => request(`/profiles?agent_id=${agentId}`),
  createProfile: (data) => request('/profiles', { method: 'POST', body: JSON.stringify(data) }),
  updateProfile: (id, data) => request(`/profiles/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  runScenario: (agentId, scenario) =>
    request('/executions/run', { method: 'POST', body: JSON.stringify({ agent_id: agentId, scenario }) }),
  getRun: (runId) => request(`/executions/${runId}`),
  startLiveSession: (agentId) =>
    request('/executions/live/start', { method: 'POST', body: JSON.stringify({ agent_id: agentId }) }),
  liveTick: (runId) =>
    request('/executions/live/tick', { method: 'POST', body: JSON.stringify({ run_id: runId }) }),
  stopLiveSession: (runId) =>
    request('/executions/live/stop', { method: 'POST', body: JSON.stringify({ run_id: runId }) }),

  listFindings: (agentId) => request(`/findings?agent_id=${agentId}`),
  listResponses: () => request('/responses'),
  approveResponse: (id, approver, reason) =>
    request(`/responses/${id}/approve`, { method: 'POST', body: JSON.stringify({ approver, reason }) }),
  rejectResponse: (id, approver, reason) =>
    request(`/responses/${id}/reject`, { method: 'POST', body: JSON.stringify({ approver, reason }) }),

  guardrailStatus: (agentId) => request(`/guardrails/status?agent_id=${agentId}`),
  auditLog: (agentId) => request(`/audit-log?agent_id=${agentId}`),
}
