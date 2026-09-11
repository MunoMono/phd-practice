const SESSION_KEY = 'innovation-design.source-interrogation.active.v1'

export const loadSourceInterrogationSession = () => {
  try {
    const stored = window.sessionStorage.getItem(SESSION_KEY)
    if (!stored) return null
    const session = JSON.parse(stored)
    return session?.traceData ? session : null
  } catch {
    return null
  }
}

export const saveSourceInterrogationSession = (session) => {
  try {
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
  } catch {
    // The active result remains usable even when browser storage is unavailable.
  }
}

export const clearSourceInterrogationSession = () => {
  try {
    window.sessionStorage.removeItem(SESSION_KEY)
  } catch {
    // Nothing else is required when browser storage is unavailable.
  }
}