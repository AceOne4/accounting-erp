function getCookie(name: string): string | null {
  const match = document.cookie.split('; ').find((c) => c.startsWith(`${name}=`))
  return match ? decodeURIComponent(match.split('=').slice(1).join('=')) : null
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
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const token = getCookie('csrftoken')
    if (token) headers.set('X-CSRFToken', token)
  }

  const res = await fetch(`/api/v1${path}`, { ...init, method, headers, credentials: 'same-origin' })
  const text = await res.text()
  const body: unknown = text ? JSON.parse(text) : null
  if (!res.ok) throw new ApiError(res.status, body)
  return body as T
}
