export function AboutPage() {
  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">About this console</div>
        <div className="page-subtitle">FLYYY.AI — AI Agent Governance</div>
      </div>

      <p className="about-lede">
        This application defines, monitors, detects, and enforces AI agent
        behaviour against an approved profile. Every action an agent
        attempts — a tool call, a data access, or a broader action — is
        checked against that agent's own approved profile <em>before</em> it
        executes. Anything outside the approved boundary is recorded as a
        finding, scored by severity, and handled through a Notify → Require
        Approval → Block response chain, with every step written to an
        audit trail.
      </p>

      <div className="card">
        <h3 className="card-title">How it works</h3>
        <p className="helper-text" style={{ marginBottom: 10 }}>
          A single governance engine sits as a choke point between an agent
          and the tools/data it wants to use. It doesn't just report
          violations after the fact — it can refuse to let a disallowed
          action happen at all.
        </p>
        <p className="helper-text" style={{ marginBottom: 0 }}>
          Flow: <b>Agent Deviation → Detection → Warning/Finding → Response
          → Block/Approval → Audit Trail.</b>
        </p>
      </div>

      <div className="card">
        <h3 className="card-title">Tech stack</h3>
        <div className="tech-grid">
          <span className="tech-chip">Python 3.12</span>
          <span className="tech-chip">FastAPI</span>
          <span className="tech-chip">PostgreSQL</span>
          <span className="tech-chip">SQLAlchemy</span>
          <span className="tech-chip">React 18</span>
          <span className="tech-chip">Vite</span>
          <span className="tech-chip">Docker Compose</span>
          <span className="tech-chip">pytest</span>
        </div>
      </div>

      <div className="card">
        <h3 className="card-title">Documentation</h3>
        <p className="helper-text" style={{ marginBottom: 0 }}>
          Full architecture diagrams, design rationale, known limitations,
          and setup instructions are in this project's <code>README.md</code>,
          with an editable system diagram at <code>docs/architecture.excalidraw</code>.
        </p>
      </div>
    </div>
  )
}
