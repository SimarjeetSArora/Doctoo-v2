/** Options for choosing how to reach someone: by email or by mobile number. */
export const CONTACT_OPTIONS = [
  { value: 'email' as const, label: 'Email' },
  { value: 'phone' as const, label: 'Mobile number' },
]

/** How a code reaches a mobile number. */
export const DELIVERY_OPTIONS = [
  { value: 'whatsapp' as const, label: 'WhatsApp' },
  { value: 'sms' as const, label: 'SMS' },
]
