import type { Message } from '../types'

interface Props {
  message: Message
}

// Format booking status into a readable badge label
function bookingBadge(status: string): { label: string; success: boolean } | null {
  if (status.startsWith('confirmed:')) {
    const id = status.replace('confirmed:', '')
    return { label: `✓ Visit booked · ${id}`, success: true }
  }
  if (status.startsWith('failed:')) {
    return { label: '✗ Booking failed', success: false }
  }
  return null
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const badge = message.bookingStatus ? bookingBadge(message.bookingStatus) : null

  return (
    <div className={`message-row ${isUser ? 'message-row--user' : 'message-row--agent'}`}>
      {!isUser && (
        <div className="avatar" aria-hidden="true">
          NS
        </div>
      )}

      <div className="bubble-group">
        <div className={`bubble ${isUser ? 'bubble--user' : 'bubble--agent'}`}>
          {message.content}
        </div>
        {badge && (
          <span className={`booking-badge ${badge.success ? 'booking-badge--success' : 'booking-badge--fail'}`}>
            {badge.label}
          </span>
        )}
      </div>
    </div>
  )
}
