import { useState, useEffect } from 'react'
import { api } from '../api/client'

const ENVIRONMENTS = ['production', 'staging', 'development']

function ChipInput({ label, values, onChange, placeholder }) {
  const [draft, setDraft] = useState('')

  const add = () => {
    const v = draft.trim()
    if (v && !values.includes(v)) onChange([...values, v])
    setDraft('')
  }

  return (
    <div className="field-row">
      <span className="field-label">{label}</span>
      <div className="tag-list" style={{ marginBottom: 8 }}>
        {values.length === 0 && <span className="tag empty">none approved</span>}
        {values.map((v) => (
          <span key={v} className="tag">
            {v}{' '}
            <button
              onClick={() => onChange(values.filter((x) => x !== v))}
              style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0, marginLeft: 4 }}
              aria-label={`Remove ${v}`}
            >×</button>
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          type="text"
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), add())}
        />
        <button className="btn" onClick={add}>Add</button>
      </div>
    </div>
  )
}

export function ProfileTab({ agent, profile, onProfileSaved }) {
  const [description, setDescription] = useState('')
  const [owner, setOwner] = useState('')
  const [environment, setEnvironment] = useState('production')
  const [tools, setTools] = useState([])
  const [dataSources, setDataSources] = useState([])
  const [actions, setActions] = useState([])
  const [maxCalls, setMaxCalls] = useState(1000)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (profile) {
      setDescription(profile.description || '')
      setOwner(profile.owner || '')
      setEnvironment(profile.environment || 'production')
      setTools(profile.allowed_tools || [])
      setDataSources(profile.allowed_data_sources || [])
      setActions(profile.allowed_actions || [])
      setMaxCalls(profile.guardrails?.max_calls_per_day?.limit ?? 1000)
    } else {
      setDescription(''); setOwner(''); setEnvironment('production')
      setTools([]); setDataSources([]); setActions([]); setMaxCalls(1000)
    }
  }, [profile?.id])

  const [saveError, setSaveError] = useState(null)

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const guardrails = {
        max_calls_per_day: { limit: Number(maxCalls), warning_pct: 80, critical_pct: 90 },
      }
      if (profile) {
        const updated = await api.updateProfile(profile.id, {
          description, owner, environment,
          allowed_tools: tools, allowed_data_sources: dataSources,
          allowed_actions: actions, guardrails,
        })
        onProfileSaved(updated)
      } else {
        const created = await api.createProfile({
          agent_id: agent.id, name: `${agent.name} - v1`,
          description, owner, environment,
          allowed_tools: tools, allowed_data_sources: dataSources,
          allowed_actions: actions, guardrails,
        })
        onProfileSaved(created)
      }
    } catch (err) {
      setSaveError(err.message || 'Failed to save profile — see browser console for details.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card">
      <h3 className="card-title">Approved Behaviour Profile</h3>
      <p className="helper-text" style={{ marginBottom: 20 }}>
        This is the baseline every execution is checked against. Anything the agent
        attempts outside these lists is flagged as a deviation.
      </p>

      <div className="field-row">
        <span className="field-label">Description</span>
        <input type="text" value={description} onChange={(e) => setDescription(e.target.value)}
          placeholder="What is this agent scoped to do, and what is it explicitly excluded from?" />
      </div>

      <div className="field-row" style={{ display: 'flex', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <span className="field-label">Owner</span>
          <input type="text" value={owner} onChange={(e) => setOwner(e.target.value)}
            placeholder="e.g. Platform Security Team" />
        </div>
        <div style={{ flex: 1 }}>
          <span className="field-label">Environment</span>
          <div className="select-inline">
            {ENVIRONMENTS.map((env) => (
              <button
                key={env}
                type="button"
                className={`pill-option ${environment === env ? 'active' : ''}`}
                onClick={() => setEnvironment(env)}
              >
                {env}
              </button>
            ))}
          </div>
        </div>
      </div>

      <ChipInput label="Allowed Tools" values={tools} onChange={setTools}
        placeholder="e.g. faq_search" />
      <ChipInput label="Allowed Data Sources" values={dataSources} onChange={setDataSources}
        placeholder="e.g. faq_database" />
      <ChipInput label="Allowed Actions" values={actions} onChange={setActions}
        placeholder="e.g. send_email" />

      <div className="field-row">
        <span className="field-label">Guardrail — Max Model Calls / Day</span>
        <input type="text" value={maxCalls} onChange={(e) => setMaxCalls(e.target.value.replace(/\D/g, ''))} />
        <p className="helper-text">Warning at 80% usage, critical at 90%.</p>
      </div>

      <div className="btn-row">
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : profile ? 'Save changes' : 'Create profile'}
        </button>
      </div>
      {saveError && (
        <p className="helper-text" style={{ color: 'var(--critical-200)', marginTop: 10 }}>
          Couldn't save: {saveError}
        </p>
      )}
    </div>
  )
}
