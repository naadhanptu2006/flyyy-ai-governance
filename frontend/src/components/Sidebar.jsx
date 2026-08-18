export function Sidebar({ agents, activeId, onSelect, onNewAgent, onDeleteRequest }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-label">Monitored Agents</div>
      {agents.length === 0 && (
        <div className="empty-state" style={{ padding: '0 20px' }}>No agents yet</div>
      )}
      {agents.map((a) => (
        <div
          key={a.id}
          className={`case-item ${a.id === activeId ? 'active' : ''}`}
          role="button"
          tabIndex={0}
          onClick={() => onSelect(a.id)}
          onKeyDown={(e) => e.key === 'Enter' && onSelect(a.id)}
        >
          <span className="case-item-main">
            <span className="case-name">{a.name}</span>
            <span className="case-id">CASE #{a.id.slice(0, 8)}</span>
          </span>
          <button
            className="case-delete-btn"
            title={`Delete ${a.name}`}
            aria-label={`Delete ${a.name}`}
            onClick={(e) => { e.stopPropagation(); onDeleteRequest(a) }}
          >
            &times;
          </button>
        </div>
      ))}
      <button className="new-case-btn" onClick={onNewAgent}>+ Register new agent</button>
    </aside>
  )
}
