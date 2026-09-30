import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'

export const MAX_MESSAGE_CHARS = 1000 // mirrors backend SendMessageSerializer

interface Props {
  onSend: (text: string) => void
  disabled: boolean
}

export default function Composer({ onSend, disabled }: Props) {
  const { t } = useTranslation()
  const [text, setText] = useState('')

  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    const value = text.trim()
    if (!value || disabled) return
    onSend(value)
    setText('')
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  const nearLimit = text.length > MAX_MESSAGE_CHARS * 0.9
  return (
    <form onSubmit={submit} className="flex items-end gap-2">
      <div className="flex-1">
        <label htmlFor="chat-input" className="sr-only">
          {t('chat.inputLabel')}
        </label>
        <textarea
          id="chat-input"
          rows={2}
          value={text}
          maxLength={MAX_MESSAGE_CHARS}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={t('chat.placeholder')}
          className="input-field resize-none text-start"
          dir="auto"
        />
        <div className={`mt-1 text-end text-xs ${nearLimit ? 'text-amber-600' : 'text-slate-400'}`}>
          {/* Isolate the "n / max" run so RTL doesn't reorder it into "max / n". */}
          <span dir="ltr">{t('chat.counter', { count: text.length, max: MAX_MESSAGE_CHARS })}</span>
        </div>
      </div>
      <button type="submit" disabled={disabled || !text.trim()} className="btn-primary mb-6">
        {t('chat.send')}
      </button>
    </form>
  )
}
