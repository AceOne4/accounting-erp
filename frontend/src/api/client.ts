function getCookie(name: string): string | null {
  const match = document.cookie.split('; ').find((c) => c.startsWith(`${name}=`))
  return match ? decodeURIComponent(match.split('=').slice(1).join('=')) : null
}

let companyId: number | null = null
/** The company every request acts in (sent as X-Company-Id). */
export function setCompanyId(id: number | null) {
  companyId = id
}

/** Flatten a DRF error body into readable lines. */
export function errorMessages(body: unknown): string[] {
  if (body == null) return []
  if (typeof body === 'string') return [body]
  if (Array.isArray(body)) return body.flatMap(errorMessages)
  if (typeof body === 'object') {
    return Object.entries(body as Record<string, unknown>).flatMap(([key, value]) => {
      const inner = errorMessages(value)
      return key === 'detail' || key === 'non_field_errors' ? inner : inner.map((m) => `${key}: ${m}`)
    })
  }
  return [String(body)]
}

export class ApiError extends Error {
  status: number
  body: unknown
  constructor(status: number, body: unknown) {
    super(`API error ${status}`)
    this.status = status
    this.body = body
  }
}

/** Same-origin JSON fetch that sends the Django session cookie and CSRF token. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (companyId !== null) headers.set('X-Company-Id', String(companyId))
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const token = getCookie('csrftoken')
    if (token) headers.set('X-CSRFToken', token)
  }

  const res = await fetch(`/api/v1${path}`, { ...init, method, headers, credentials: 'same-origin' })
  const text = await res.text()
  let body: unknown = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text.slice(0, 200)
    }
  }
  if (!res.ok) throw new ApiError(res.status, body)
  return body as T
}
