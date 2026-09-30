import type { DoctorCard, Emergency, Turn } from '../api/types'

export const doctor: DoctorCard = {
  provider_id: 1,
  name_en: 'Dr. Faisal Al-Harbi',
  name_ar: 'د. فيصل الحربي',
  specialties: [{ code: 'CARDIOLOGY', name_en: 'Cardiology', name_ar: 'أمراض القلب' }],
  hospital: {
    hospital_id: 1,
    name_en: 'Al-Wahah Medical City',
    name_ar: 'مدينة الواحة الطبية',
    city: 'RIYADH',
    city_name_en: 'Riyadh',
    city_name_ar: 'الرياض',
    address_en: 'King Fahd Road',
    address_ar: 'طريق الملك فهد',
    has_emergency: true,
    emergency_phone: '+966 11 000 0101',
    accreditation: 'JCI',
  },
  languages: ['ar', 'en'],
  years_experience: 18,
  offers_second_opinion: true,
  offers_telemedicine: false,
  consultation_fee_sar: '450.00',
  rating: '4.8',
  next_available: '2026-10-02T06:00:00Z',
}

export const emergency: Emergency = {
  numbers: [
    { number: '997', label_en: 'Ambulance (Saudi Red Crescent)', label_ar: 'الإسعاف (الهلال الأحمر السعودي)' },
    { number: '911', label_en: 'Unified emergency number', label_ar: 'رقم الطوارئ الموحد' },
  ],
  hospitals: [doctor.hospital],
}

export const turn: Turn = {
  message_id: 10,
  reply_text: 'Here are verified options.',
  urgency: 'URGENT',
  urgency_source: 'rules',
  next_step: 'SEE_SPECIALIST',
  clarifying_questions: [],
  providers: [doctor],
  emergency: null,
  reasoning_summary: 'Chest pain without red flags: cardiology visit.',
  trace: {
    state: { chief_complaint: 'chest pain', city: 'RIYADH' },
    stage: 'RECOMMEND',
    tool_calls: [
      { name: 'search_providers', args: { specialty: 'CARDIOLOGY' }, result_ids: [1, 3], latency_ms: 12, success: true, error: '' },
    ],
    iterations: 2,
    grounding_violations: [{ type: 'unknown_provider_id', provider_id: 999 }],
    rules: { level: 'URGENT', matched_flags: ['CHEST_PAIN'] },
    llm_provider: 'mock',
    llm_model: 'mock-scripted',
    outcome: 'ok',
    fallback_reason: '',
    latency_ms: 40,
    clarification_rounds: 1,
  },
  disclaimer: { en: 'Not medical advice.', ar: 'ليست نصيحة طبية.' },
}
