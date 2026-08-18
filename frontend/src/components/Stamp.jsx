export function Stamp({ children, kind }) {
  return <span className={`stamp stamp-${kind}`}>{children}</span>
}

export function severityStampKind(sev) {
  return sev // 'low' | 'medium' | 'high' map directly to stamp-low/medium/high
}

export function statusStampKind(status) {
  const map = {
    pending: 'pending',
    approved: 'approved',
    rejected: 'rejected',
    auto_resolved: 'executed',
    blocked: 'blocked',
    executed: 'executed',
    require_approval: 'pending',
    notify: 'executed',
    block: 'blocked',
  }
  return map[status] || 'pending'
}
