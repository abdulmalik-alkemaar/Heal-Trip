// Types mirroring the backend API (backend/assistant/api/serializers.py,
// backend/providers/serializers.py). OpenAPI: /api/docs/ (docs/openapi.yaml).

export type Language = 'en' | 'ar'
export type Urgency = 'EMERGENCY' | 'URGENT' | 'ROUTINE' | 'UNKNOWN'
export type UrgencySource = 'rules' | 'llm' | 'fallback'
export type NextStep =
  | 'CALL_EMERGENCY'
  | 'GO_TO_ER'
  | 'SEE_SPECIALIST'
  | 'SECOND_OPINION'
  | 'NEED_MORE_INFO'
export type Stage = 'INTAKE' | 'CLARIFY' | 'ASSESS' | 'SEARCH' | 'RECOMMEND' | 'EMERGENCY'

export interface Bilingual {
  en: string
  ar: string
}

export interface Specialty {
  code: string
  name_en: string
  name_ar: string
}

export interface HospitalCard {
  hospital_id: number
  name_en: string
  name_ar: string
  city: string
  city_name_en: string
  city_name_ar: string
  address_en: string
  address_ar: string
  has_emergency: boolean
  emergency_phone: string
  accreditation: string
}

export interface DoctorCard {
  provider_id: number
  name_en: string
  name_ar: string
  specialties: Specialty[]
  hospital: HospitalCard
  languages: Language[]
  years_experience: number
  offers_second_opinion: boolean
  offers_telemedicine: boolean
  consultation_fee_sar: string
  rating: string | null
  next_available: string | null
}

export interface EmergencyNumber {
  number: string
  label_en: string
  label_ar: string
}

export interface Emergency {
  numbers: EmergencyNumber[]
  hospitals: HospitalCard[]
}

export interface ClarifyingQuestion {
  question: string
  quick_replies: string[]
}

export interface ToolCallTrace {
  name: string
  args: Record<string, unknown>
  result_ids: number[]
  latency_ms: number
  success: boolean
  error: string
}

export interface GroundingViolation {
  type: string
  provider_id?: number
  hospital_id?: number
  text?: string
}

export interface Trace {
  state: Record<string, unknown>
  stage: Stage
  tool_calls: ToolCallTrace[]
  iterations: number
  grounding_violations: GroundingViolation[]
  rules: { level: Urgency; matched_flags: string[] }
  llm_provider: string
  llm_model: string
  outcome: 'ok' | 'emergency_short_circuit' | 'fallback'
  fallback_reason: string
  latency_ms: number
  clarification_rounds: number
}

export interface Turn {
  message_id: number
  reply_text: string
  urgency: Urgency
  urgency_source: UrgencySource
  next_step: NextStep
  clarifying_questions: ClarifyingQuestion[]
  providers: DoctorCard[]
  emergency: Emergency | null
  reasoning_summary: string
  trace: Trace
  disclaimer: Bilingual
}

export interface SessionCreated {
  session_id: string
  language: Language
  created_at: string
  disclaimer: Bilingual
}

export interface HistoryMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
  turn: Turn | null
}

export interface SessionDetail {
  session_id: string
  language: Language
  state: Record<string, unknown>
  stage: Stage
  urgency_level: Urgency
  clarification_rounds: number
  messages_remaining: number
  messages: HistoryMessage[]
}

export interface ApiErrorBody {
  error: {
    code: string
    message_en: string
    message_ar: string
    details?: Record<string, unknown>
  }
}
