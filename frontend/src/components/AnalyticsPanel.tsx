import { useState, useCallback } from 'react'
import { fetchAnalytics } from '../api'
import type { ConversationAnalytics } from '../types'

interface Props {
  sessionId: string | null
}

type Status = 'idle' | 'loading' | 'success' | 'error'

// ── Helpers ──────────────────────────────────────────────────────────────

function val(v: string | null | undefined): string {
  return v?.trim() ? v.trim() : 'Not provided'
}

function visitStatusLabel(status: string | null): { text: string; cls: string } {
  switch (status) {
    case 'confirmed':     return { text: 'Confirmed',     cls: 'badge--green'  }
    case 'failed':        return { text: 'Booking failed', cls: 'badge--red'    }
    case 'requested':     return { text: 'Requested',     cls: 'badge--blue'   }
    case 'awaiting_date': return { text: 'Awaiting date', cls: 'badge--grey'   }
    case 'awaiting_time': return { text: 'Awaiting time', cls: 'badge--grey'   }
    case 'ready_to_book': return { text: 'Ready to book', cls: 'badge--blue'   }
    case 'not_requested': return { text: 'Not requested', cls: 'badge--grey'   }
    default:              return { text: val(status),     cls: 'badge--grey'   }
  }
}

function qualityBadge(v: string | null): { text: string; cls: string } {
  switch (v?.toLowerCase()) {
    case 'hot':  return { text: 'Hot',  cls: 'badge--red'   }
    case 'warm': return { text: 'Warm', cls: 'badge--amber' }
    case 'cold': return { text: 'Cold', cls: 'badge--grey'  }
    default:     return { text: 'Unknown', cls: 'badge--grey' }
  }
}

function levelBadge(v: string | null): { text: string; cls: string } {
  switch (v?.toLowerCase()) {
    case 'high':   return { text: 'High',   cls: 'badge--green' }
    case 'medium': return { text: 'Medium', cls: 'badge--amber' }
    case 'low':    return { text: 'Low',    cls: 'badge--grey'  }
    default:       return { text: 'Unknown', cls: 'badge--grey' }
  }
}

function outcomeBadge(v: string | null): { text: string; cls: string } {
  switch (v) {
    case 'visit_booked':        return { text: 'Visit booked',        cls: 'badge--green' }
    case 'follow_up_scheduled': return { text: 'Follow-up scheduled', cls: 'badge--blue'  }
    case 'not_interested':      return { text: 'Not interested',      cls: 'badge--grey'  }
    case 'stopped':             return { text: 'Stopped',             cls: 'badge--red'   }
    case 'escalated':           return { text: 'Escalated',           cls: 'badge--amber' }
    case 'in_progress':         return { text: 'In progress',         cls: 'badge--blue'  }
    default:                    return { text: val(v),                cls: 'badge--grey'  }
  }
}

// ── Sub-components ────────────────────────────────────────────────────────

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="ap-row">
      <span className="ap-label">{label}</span>
      <span className="ap-value">{children}</span>
    </div>
  )
}

function Badge({ text, cls }: { text: string; cls: string }) {
  return <span className={`ap-badge ${cls}`}>{text}</span>
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="ap-section">
      <div className="ap-section-title">{title}</div>
      {children}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────

export default function AnalyticsPanel({ sessionId }: Props) {
  const [status, setStatus] = useState<Status>('idle')
  const [data, setData] = useState<ConversationAnalytics | null>(null)
  const [analyticsError, setAnalyticsError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!sessionId) return
    setStatus('loading')
    setAnalyticsError(null)
    try {
      const res = await fetchAnalytics(sessionId)
      setData(res.analytics)
      setStatus('success')
    } catch (err) {
      setAnalyticsError('Unable to load analytics.')
      setStatus('error')
    }
  }, [sessionId])

  // ── No session yet ───────────────────────────────────────────────────
  if (!sessionId) {
    return (
      <div className="ap-empty">
        <div className="ap-empty-icon">📋</div>
        <p>Start a conversation to generate analytics.</p>
      </div>
    )
  }

  // ── Idle (not yet loaded) ────────────────────────────────────────────
  if (status === 'idle') {
    return (
      <div className="ap-empty">
        <div className="ap-empty-icon">📋</div>
        <p>Analytics will appear here after the conversation.</p>
        <button className="ap-btn ap-btn--primary" onClick={load}>
          Generate Analytics
        </button>
      </div>
    )
  }

  // ── Loading ──────────────────────────────────────────────────────────
  if (status === 'loading') {
    return (
      <div className="ap-empty">
        <div className="ap-spinner" aria-label="Loading" />
        <p className="ap-loading-text">Generating analytics…</p>
      </div>
    )
  }

  // ── Error ────────────────────────────────────────────────────────────
  if (status === 'error') {
    return (
      <div className="ap-empty">
        <div className="ap-empty-icon">⚠️</div>
        <p>{analyticsError}</p>
        <button className="ap-btn ap-btn--primary" onClick={load}>
          Try Again
        </button>
      </div>
    )
  }

  // ── Success ──────────────────────────────────────────────────────────
  if (!data) return null

  const visitStatus = visitStatusLabel(data.site_visit_status)
  const quality = qualityBadge(data.lead_quality)
  const interest = levelBadge(data.interest_level)
  const outcome = outcomeBadge(data.conversation_outcome)

  return (
    <div className="ap-content">
      {/* Header row with refresh */}
      <div className="ap-header-row">
        <span className="ap-agent-label">Agent View · Lead Analytics</span>
        <button className="ap-btn ap-btn--ghost" onClick={load}>
          ↻ Refresh
        </button>
      </div>

      {/* Summary */}
      {data.summary && (
        <div className="ap-summary">{data.summary}</div>
      )}

      {/* Customer */}
      <Section title="Customer">
        <Row label="Name">{val(data.name)}</Row>
        <Row label="Language">{val(data.language)}</Row>
      </Section>

      {/* Requirements */}
      <Section title="Requirements">
        <Row label="Configuration">{val(data.configuration)}</Row>
        <Row label="Budget">{data.budget ? `₹${data.budget}` : 'Not provided'}</Row>
        <Row label="Purpose">{val(data.purpose)}</Row>
        <Row label="Location">{val(data.location_preference)}</Row>
        <Row label="Timeline">{val(data.timeline)}</Row>
      </Section>

      {/* Lead assessment */}
      <Section title="Lead Assessment">
        <Row label="Interest">
          <Badge text={interest.text} cls={interest.cls} />
        </Row>
        <Row label="Lead quality">
          <Badge text={quality.text} cls={quality.cls} />
        </Row>
        <Row label="Objections">
          {data.objections.length === 0
            ? <span className="ap-muted">No objections identified</span>
            : (
              <div className="ap-chips">
                {data.objections.map(o => (
                  <span key={o} className="ap-chip">{o.replace(/_/g, ' ')}</span>
                ))}
              </div>
            )
          }
        </Row>
      </Section>

      {/* Site visit */}
      <Section title="Site Visit">
        <Row label="Status">
          <Badge text={visitStatus.text} cls={visitStatus.cls} />
        </Row>
        {data.site_visit_date && <Row label="Date">{data.site_visit_date}</Row>}
        {data.site_visit_time && <Row label="Time">{data.site_visit_time}</Row>}
        <Row label="Booking ID">
          {data.booking_id
            ? <span className="ap-booking-id">{data.booking_id}</span>
            : <span className="ap-muted">Not available</span>
          }
        </Row>
      </Section>

      {/* Follow-up */}
      <Section title="Follow-up">
        <Row label="Required">
          {data.follow_up_required
            ? <Badge text="Yes" cls="badge--amber" />
            : <Badge text="No"  cls="badge--grey"  />
          }
        </Row>
        {data.follow_up_required && (
          <Row label="Time">{val(data.follow_up_time)}</Row>
        )}
      </Section>

      {/* Status */}
      <Section title="Status">
        <Row label="Communication">{val(data.communication_status)}</Row>
        <Row label="Escalation">
          {data.human_escalation
            ? <Badge text="Requested" cls="badge--amber" />
            : <Badge text="None"      cls="badge--grey"  />
          }
        </Row>
        <Row label="Outcome">
          <Badge text={outcome.text} cls={outcome.cls} />
        </Row>
      </Section>
    </div>
  )
}
