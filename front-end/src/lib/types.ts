// Shapes returned by the backend (mirror the Pydantic schemas in back-end/app/schemas).

export type Role = 'owner' | 'doctor' | 'receptionist'

export const ROLE_LABELS: Record<Role, string> = {
  owner: 'Owner',
  doctor: 'Doctor',
  receptionist: 'Receptionist',
}

export type TokenResponse = { access_token: string; token_type: string }

export type Salutation = 'Dr.' | 'Mr.' | 'Mrs.' | 'Ms.' | 'Miss' | 'Prof.'

export type User = {
  id: string
  email: string
  salutation: Salutation | null
  first_name: string
  middle_name: string | null
  last_name: string
  full_name: string
  phone: string | null
  email_verified: boolean
  phone_verified: boolean
}

export type Membership = { clinic_id: string; clinic_name: string; role: Role }

export type Me = { user: User; memberships: Membership[] }

export type Clinic = {
  id: string
  name: string
  timezone: string
  phone: string | null
  email: string | null
  address: string | null
  city: string | null
  state: string | null
  pincode: string | null
  gstin: string | null
}

export type Member = {
  id: string
  user_id: string
  full_name: string
  email: string
  phone: string | null
  role: Role
  is_active: boolean
  joined_at: string
}

export type Invitation = {
  id: string
  email: string | null
  phone: string | null
  role: Role
  invited_by_name: string
  created_at: string
  expires_at: string
}

export type OtpChannel = 'email' | 'phone'

export type PhoneDelivery = 'whatsapp' | 'sms'

export type AuthOptions = { phone_code_channels: PhoneDelivery[] }

export type OtpResponse = { detail: string; expires_in_minutes: number; resend_after_seconds: number }

export type InvitationLookup = {
  clinic_id: string
  clinic_name: string
  channel: OtpChannel
  email: string | null
  phone: string | null
  role: Role
  invited_by_name: string
  needs_name: boolean
  needs_password: boolean
  needs_email: boolean
}
