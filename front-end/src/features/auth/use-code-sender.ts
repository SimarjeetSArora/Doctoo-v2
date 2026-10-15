import { useEffect, useState } from 'react'

import { api } from '@/lib/api'
import type { OtpChannel, OtpResponse, PhoneDelivery } from '@/lib/types'

type Purpose = 'register' | 'login'

/** Sends one-time codes and tracks where the last one went plus the resend countdown. */
export function useCodeSender(purpose: Purpose) {
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [cooldown, setCooldown] = useState(0)
  const [ttlMinutes, setTtlMinutes] = useState(10)
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setTimeout(() => setCooldown((s) => s - 1), 1000)
    return () => clearTimeout(timer)
  }, [cooldown])

  /** Throws ApiError on failure (e.g. "Please wait 42 seconds…"). */
  async function send(
    channel: OtpChannel,
    target: string,
    delivery: PhoneDelivery = 'whatsapp',
  ): Promise<OtpResponse> {
    setSending(true)
    try {
      const response = await api.post<OtpResponse>('/auth/otp', {
        channel,
        target,
        purpose,
        delivery,
      })
      setSentTo(target)
      setTtlMinutes(response.expires_in_minutes)
      setCooldown(response.resend_after_seconds)
      return response
    } finally {
      setSending(false)
    }
  }

  function reset() {
    setSentTo(null)
  }

  /** Label for the send / resend button. */
  function buttonLabel(target: string, idle = 'Send code'): string {
    if (sending) return 'Sending…'
    if (sentTo !== target) return idle
    return cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend code'
  }

  return { send, reset, sentTo, cooldown, ttlMinutes, sending, buttonLabel }
}
