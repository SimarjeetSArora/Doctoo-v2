// All backend calls go through here. It attaches the access token and clinic id,
// and transparently refreshes an expired access token once.
const API_BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Kept in memory only (not localStorage), so injected scripts can't read it from storage.
let accessToken: string | null = null
let clinicId: string | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function setClinicId(id: string | null) {
  clinicId = id
}

type TokenResponse = { access_token: string; token_type: string }

let refreshInFlight: Promise<boolean> | null = null

/** Gets a new access token using the httpOnly refresh cookie. Concurrent calls share one request. */
export function refreshAccessToken(): Promise<boolean> {
  refreshInFlight ??= fetch(`${API_BASE}/auth/refresh`, { method: 'POST' })
    .then(async (response) => {
      if (!response.ok) {
        accessToken = null
        return false
      }
      accessToken = ((await response.json()) as TokenResponse).access_token
      return true
    })
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null
    })
  return refreshInFlight
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    // FastAPI returns { detail: "message" } or, for validation errors, { detail: [{ msg }] }
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg
  } catch {
    // not JSON
  }
  return `Something went wrong (${response.status})`
}

export async function apiFetch<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  if (clinicId) headers.set('X-Clinic-Id', clinicId)

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })

  if (response.status === 401 && retry && accessToken && (await refreshAccessToken())) {
    return apiFetch<T>(path, init, false)
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  if (response.status === 204 || response.status === 202) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    apiFetch<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T = void>(path: string) => apiFetch<T>(path, { method: 'DELETE' }),
}
