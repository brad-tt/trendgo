type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

function formatErrorDetail(detail: unknown): string {
  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') {
          return item
        }
        if (item && typeof item === 'object') {
          const record = item as { loc?: unknown; msg?: unknown }
          const loc = Array.isArray(record.loc) ? record.loc.join('.') : ''
          const msg = typeof record.msg === 'string' ? record.msg : ''
          if (loc && msg) {
            return `${loc}: ${msg}`
          }
          if (msg) {
            return msg
          }
        }
        return ''
      })
      .filter(Boolean)
    if (messages.length) {
      return messages.join('；')
    }
  }

  if (detail && typeof detail === 'object') {
    const message = Reflect.get(detail, 'message')
    if (typeof message === 'string') {
      return message
    }
    try {
      return JSON.stringify(detail)
    } catch {
      return '请求失败，请检查输入。'
    }
  }

  return ''
}

async function request<T>(method: HttpMethod, url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    const contentType = response.headers.get('content-type') || ''
    if (contentType.includes('application/json')) {
      const payload = (await response.json()) as { detail?: unknown }
      const detail = formatErrorDetail(payload.detail)
      throw new Error(detail || `${method} ${url} failed with ${response.status}`)
    }
    const detail = await response.text()
    throw new Error(detail || `${method} ${url} failed with ${response.status}`)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export const apiClient = {
  get<T>(url: string) {
    return request<T>('GET', url)
  },
  post<T>(url: string, body?: unknown) {
    return request<T>('POST', url, body)
  },
  put<T>(url: string, body?: unknown) {
    return request<T>('PUT', url, body)
  },
  delete<T>(url: string) {
    return request<T>('DELETE', url)
  },
}
