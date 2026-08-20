// Matches backend CustomerContext (models.py)
export interface CustomerState {
  name: string | null
  language: string | null
  configuration: string | null
  budget: string | null
  purpose: string | null
  location_preference: string | null
  timeline: string | null
  interest_level: string | null
  lead_quality: string | null
  objections: string[]
  site_visit_requested: boolean
  site_visit_date: string | null
  site_visit_time: string | null
  site_visit_status: string
  follow_up_required: boolean
  follow_up_time: string | null
  human_escalation: boolean
  communication_status: string
}

// Matches backend ConversationAnalytics (models.py)
export interface ConversationAnalytics {
  name: string | null
  language: string | null
  configuration: string | null
  budget: string | null
  purpose: string | null
  location_preference: string | null
  timeline: string | null
  interest_level: string | null
  lead_quality: string | null
  objections: string[]
  site_visit_requested: boolean
  site_visit_status: string | null
  site_visit_date: string | null
  site_visit_time: string | null
  booking_id: string | null
  follow_up_required: boolean
  follow_up_time: string | null
  human_escalation: boolean
  communication_status: string | null
  conversation_outcome: string | null
  summary: string | null
}

// Matches backend AnalyticsResponse
export interface AnalyticsResponse {
  session_id: string
  analytics: ConversationAnalytics
  error: string | null
}

// Matches backend ChatRequest
export interface ChatRequest {
  session_id?: string | null
  message: string
}

// Matches backend ChatResponse
export interface ChatResponse {
  session_id: string
  message: string
  customer_state: CustomerState
  booking_status: string | null
  communication_active: boolean
  error: string | null
}

// UI-only message shape (not sent to backend)
export type MessageRole = 'user' | 'assistant'

export interface Message {
  id: string
  role: MessageRole
  content: string
  bookingStatus?: string | null  // shown as badge when a booking occurred
}
