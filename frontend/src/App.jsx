import { useEffect, useState } from 'react'
import { api } from './api/client.js'
import { Sidebar } from './components/Sidebar.jsx'
import { ProfileTab } from './components/ProfileTab.jsx'
import { RunConsoleTab } from './components/RunConsoleTab.jsx'
import { FindingsTab } from './components/FindingsTab.jsx'
import { AuditTab } from './components/AuditTab.jsx'
import { LogsPage } from './components/LogsPage.jsx'
import { SettingsPage } from './components/SettingsPage.jsx'
import { AboutPage } from './components/AboutPage.jsx'
import { ConfirmDialog } from './components/ConfirmDialog.jsx'

const TABS = ['Profile', 'Run Console', 'Findings & Approvals', 'Audit Trail']
const NAV_ITEMS = [
  { key: 'agents', label: 'Agents', icon: '\u25A3' },
  { key: 'logs', label: 'Logs', icon: '\u2261' },
  { key: 'settings', label: 'Settings', icon: '\u2699' },
  { key: 'about', label: 'About', icon: '\u24D8' },
]

function NewAgentForm({ onCreated, onCancel }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    try {
      const agent = await api.createAgent({ name, description })
      onCreated(agent)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="dossier">
      <div className="dossier-header">
        <div>
          <div className="dossier-title">Register New Agent</div>
          <div className="dossier-meta">A case file will be opened for this agent</div>
        </div>
      </div>
      <form className="card" onSubmit={submit} style={{ maxWidth: 480 }}>
        <div className="field-row">
          <span className="field-label">Agent Name</span>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Customer Support Agent" autoFocus />
        </div>
        <div className="field-row">
          <span className="field-label">Description</span>
          <input type="text" value={description} onChange={(e) => setDescription(e.target.value)}
            placeholder="What does this agent do?" />
        </div>
        <div className="btn-row">
          <button type="submit" className="btn btn-primary" disabled={saving || !name.trim()}>
            {saving ? 'Creating…' : 'Open case file'}
          </button>
          <button type="button" className="btn" onClick={onCancel}>Cancel</button>
        </div>
      </form>
    </div>
  )
}

export default function App() {
  const [view, setView] = useState('agents')
  const [agents, setAgents] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [profile, setProfile] = useState(null)
  const [tab, setTab] = useState(TABS[0])
  const [showNewAgent, setShowNewAgent] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [loading, setLoading] = useState(true)
  const [pendingDelete, setPendingDelete] = useState(null)

  const loadAgents = async (selectId) => {
    const list = await api.listAgents()
    setAgents(list)
    if (selectId) setActiveId(selectId)
    else if (!activeId && list.length) setActiveId(list[0].id)
    setLoading(false)
  }

  useEffect(() => { loadAgents() }, [])

  useEffect(() => {
    if (!activeId) { setProfile(null); return }
    api.listProfiles(activeId).then((profiles) => setProfile(profiles[0] || null))
  }, [activeId, refreshKey])

  const activeAgent = agents.find((a) => a.id === activeId)

  const handleProfileSaved = async (savedProfile) => {
    setProfile(savedProfile)
    if (activeAgent && !activeAgent.active_profile_id) {
      await api.activateProfile(activeAgent.id, savedProfile.id)
    }
    setRefreshKey((k) => k + 1)
  }

  const confirmDelete = async () => {
    const agent = pendingDelete
    setPendingDelete(null)
    await api.deleteAgent(agent.id)
    const list = await api.listAgents()
    setAgents(list)
    if (activeId === agent.id) {
      setActiveId(list.length ? list[0].id : null)
    }
  }

  const selectAgent = (id) => {
    setActiveId(id); setShowNewAgent(false); setTab(TABS[0]); setView('agents')
  }

  return (
    <div className="app-shell">
      <div className="app-header">
        <div className="app-header-left">
          <svg className="app-logo-mark" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M16 16L4 8L16 4L16 16Z" fill="var(--brand-green)" />
            <path d="M16 16L28 8L16 4L16 16Z" fill="var(--brand-teal)" />
            <path d="M16 16L4 24L16 28L16 16Z" fill="var(--brand-blue)" />
            <path d="M16 16L28 24L16 28L16 16Z" fill="#7a6ff0" />
          </svg>
          <span className="app-mark">FLYYY.AI</span>
          <span className="app-subtitle">Agent Governance Console</span>
        </div>
      </div>

      <nav className="top-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            className={`top-nav-btn ${view === item.key ? 'active' : ''}`}
            onClick={() => setView(item.key)}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      {view === 'logs' && <LogsPage agents={agents} />}
      {view === 'settings' && <SettingsPage agentCount={agents.length} />}
      {view === 'about' && <AboutPage />}

      {view === 'agents' && (
        <div className="app-body">
          <Sidebar
            agents={agents}
            activeId={showNewAgent ? null : activeId}
            onSelect={selectAgent}
            onNewAgent={() => setShowNewAgent(true)}
            onDeleteRequest={(agent) => setPendingDelete(agent)}
          />

          {showNewAgent && (
            <NewAgentForm
              onCreated={(agent) => { setShowNewAgent(false); loadAgents(agent.id) }}
              onCancel={() => setShowNewAgent(false)}
            />
          )}

          {!showNewAgent && loading && <div className="dossier"><div className="empty-state">Loading…</div></div>}

          {!showNewAgent && !loading && !activeAgent && (
            <div className="dossier">
              <div className="empty-state">No agents registered yet. Open a case file to begin.</div>
            </div>
          )}

          {!showNewAgent && activeAgent && (
            <div className="dossier">
              <div className="dossier-header">
                <div>
                  <div className="dossier-title" style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
                    <span>{activeAgent.name}</span>
                    {profile && <span className="stamp stamp-executed" style={{ verticalAlign: 'middle' }}>{profile.environment}</span>}
                  </div>
                  <div className="dossier-meta">
                    CASE #{activeAgent.id.slice(0, 8)}
                    <span className="sep">|</span>
                    {activeAgent.description || 'No description on file'}
                    <span className="sep">|</span>
                    {profile ? `Profile: ${profile.name}${profile.owner ? ` · Owner: ${profile.owner}` : ''}` : 'No active profile'}
                  </div>
                </div>
              </div>

              <div className="tabs">
                {TABS.map((t) => (
                  <button key={t} className={`tab-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
                    {t}
                  </button>
                ))}
              </div>

              {tab === 'Profile' && (
                <ProfileTab agent={activeAgent} profile={profile} onProfileSaved={handleProfileSaved} />
              )}
              {tab === 'Run Console' && (
                <RunConsoleTab agent={activeAgent} profile={profile} onRunComplete={() => setRefreshKey((k) => k + 1)} />
              )}
              {tab === 'Findings & Approvals' && (
                <FindingsTab agent={activeAgent} refreshKey={refreshKey} />
              )}
              {tab === 'Audit Trail' && (
                <AuditTab agent={activeAgent} refreshKey={refreshKey} />
              )}
            </div>
          )}
        </div>
      )}

      {pendingDelete && (
        <ConfirmDialog
          title="Delete this agent?"
          message={`This permanently removes "${pendingDelete.name}" — its profile, execution history, findings, responses, and audit entries. This cannot be undone.`}
          confirmLabel="Delete agent"
          onConfirm={confirmDelete}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </div>
  )
}
