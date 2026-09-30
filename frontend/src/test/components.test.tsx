import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import EmergencyPanel from '../components/chat/EmergencyPanel'
import ProviderCard from '../components/chat/ProviderCard'
import QuickReplies from '../components/chat/QuickReplies'
import TracePanel from '../components/chat/TracePanel'
import UrgencyBanner from '../components/chat/UrgencyBanner'
import LanguageToggle from '../components/LanguageToggle/LanguageToggle'
import i18n from '../i18n'
import { doctor, emergency, turn } from './fixtures'

describe('RTL / language switching', () => {
  it('toggles <html lang dir> between en/ltr and ar/rtl', async () => {
    render(<LanguageToggle />)
    expect(document.documentElement.dir).toBe('ltr')

    await userEvent.click(screen.getByRole('button', { name: 'Switch to Arabic' }))
    expect(document.documentElement.lang).toBe('ar')
    expect(document.documentElement.dir).toBe('rtl')

    await userEvent.click(screen.getByRole('button', { name: 'التبديل إلى الإنجليزية' }))
    expect(document.documentElement.dir).toBe('ltr')
  })
})

describe('ProviderCard (DB-rendered)', () => {
  it('renders directory fields in English', () => {
    render(<ProviderCard doctor={doctor} />)
    expect(screen.getByRole('heading', { name: 'Dr. Faisal Al-Harbi' })).toBeInTheDocument()
    expect(screen.getByText('Cardiology')).toBeInTheDocument()
    expect(screen.getByText(/Al-Wahah Medical City — Riyadh/)).toBeInTheDocument()
    expect(screen.getByText('Second opinion')).toBeInTheDocument()
    expect(screen.queryByText('Telemedicine')).not.toBeInTheDocument()
    expect(screen.getByText('450 SAR')).toBeInTheDocument()
    expect(screen.getByText('18 years experience')).toBeInTheDocument()
  })

  it('switches to the Arabic DB fields', async () => {
    await act(() => i18n.changeLanguage('ar'))
    render(<ProviderCard doctor={doctor} />)
    expect(screen.getByRole('heading', { name: 'د. فيصل الحربي' })).toBeInTheDocument()
    expect(screen.getByText('أمراض القلب')).toBeInTheDocument()
    expect(screen.getByText('رأي ثانٍ')).toBeInTheDocument()
  })

  it('shows a clear message when there is no open slot', () => {
    render(<ProviderCard doctor={{ ...doctor, next_available: null }} />)
    expect(screen.getByText('No open slots in the next 14 days')).toBeInTheDocument()
  })
})

describe('UrgencyBanner + EmergencyPanel', () => {
  it('EMERGENCY shows an alert with tap-to-call 997', () => {
    render(<UrgencyBanner urgency="EMERGENCY" nextStep="CALL_EMERGENCY" />)
    expect(screen.getByRole('alert')).toHaveAttribute('data-urgency', 'EMERGENCY')
    expect(screen.getByRole('link', { name: /Call 997 now/ })).toHaveAttribute('href', 'tel:997')
  })

  it('URGENT is a status (no call button)', () => {
    render(<UrgencyBanner urgency="URGENT" nextStep="SEE_SPECIALIST" />)
    expect(screen.getByRole('status')).toHaveTextContent('Urgent')
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('lists emergency numbers and ER hospitals', () => {
    render(<EmergencyPanel emergency={emergency} />)
    expect(screen.getByRole('link', { name: /997/ })).toHaveAttribute('href', 'tel:997')
    expect(screen.getByRole('link', { name: /911/ })).toHaveAttribute('href', 'tel:911')
    expect(screen.getByText('Al-Wahah Medical City')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '+966 11 000 0101' })).toHaveAttribute('href', 'tel:+966110000101')
  })
})

describe('QuickReplies', () => {
  it('sends the chip text when tapped', async () => {
    const onPick = vi.fn()
    render(
      <QuickReplies
        questions={[{ question: 'Does the pain spread?', quick_replies: ['Yes, to my left arm', 'No'] }]}
        onPick={onPick}
        disabled={false}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Yes, to my left arm' }))
    expect(onPick).toHaveBeenCalledWith('Yes, to my left arm')
  })
})

describe('TracePanel', () => {
  it('shows stage, urgency source, tool calls and grounding violations', () => {
    render(<TracePanel turn={turn} />)
    expect(screen.getByText('Recommend')).toBeInTheDocument()
    expect(screen.getByText('deterministic rules')).toBeInTheDocument()
    expect(screen.getByText('search_providers')).toBeInTheDocument()
    expect(screen.getByText(/result ids: \[1, 3\]/)).toBeInTheDocument()
    expect(screen.getByText(/unknown_provider_id/)).toBeInTheDocument()
  })

  it('has an empty state before the first reply', () => {
    render(<TracePanel turn={null} />)
    expect(screen.getByText(/Send a message/)).toBeInTheDocument()
  })
})
