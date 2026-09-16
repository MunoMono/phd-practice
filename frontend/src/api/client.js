import getApiBaseUrl from '../utils/apiBaseUrl'

const buildQueryString = (params = {}) => {
  const searchParams = new URLSearchParams()

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return
    }

    if (Array.isArray(value)) {
      value.forEach((item) => searchParams.append(key, item))
      return
    }

    searchParams.append(key, value)
  })

  const query = searchParams.toString()
  return query ? `?${query}` : ''
}

export const apiRequest = async (path, options = {}) => {
  const {
    method = 'GET',
    params,
    body,
    headers = {},
    signal,
    timeoutMs
  } = options

  const timeoutController = timeoutMs ? new AbortController() : null
  const timeout = timeoutController && setTimeout(() => timeoutController.abort(), timeoutMs)

  const baseUrl = getApiBaseUrl()
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const response = await fetch(`${baseUrl}${normalizedPath}${buildQueryString(params)}`, {
    method,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...headers
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: signal || timeoutController?.signal
  })

  if (timeout) clearTimeout(timeout)

  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json')
    ? await response.json()
    : await response.text()

  if (!response.ok) {
    const message = response.status === 504
      ? 'Interrogation timed out before the analysis pipeline completed. No formal research run was created.'
      : typeof payload === 'string'
      ? 'The research service returned an unexpected response.'
      : payload?.detail || payload?.message || response.statusText
    const error = new Error(message)
    error.status = response.status
    error.payload = payload
    throw error
  }

  return payload
}

export default apiRequest