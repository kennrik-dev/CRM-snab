export type ApiError = { status: number; body: any }

type FetchOptions = {
  method?: string
  body?: unknown
  headers?: Record<string, string>
}

async function parseResponse(res: Response): Promise<any> {
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  opts: FetchOptions = {},
): Promise<T> {
  const { method = 'GET', body, headers = {} } = opts

  const init: RequestInit = {
    method,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  }

  if (body !== undefined) {
    init.body = JSON.stringify(body)
  }

  const res = await fetch(`/api${path}`, init)

  if (res.status === 401) {
    window.dispatchEvent(new CustomEvent('auth:logout'))
  }

  const data = await parseResponse(res)

  if (!res.ok) {
    throw { status: res.status, body: data } satisfies ApiError
  }

  return data as T
}