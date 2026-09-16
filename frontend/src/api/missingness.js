import apiRequest from './client'

export const getMissingnessSummary = () => apiRequest('/api/missingness/summary')

export const getMissingnessEvents = (params = {}) => apiRequest('/api/missingness/events', { params })

export const createMissingnessEvent = (payload) => apiRequest('/api/missingness/events', {
  method: 'POST',
  body: payload
})

export const updateMissingnessEvent = (eventId, payload) => apiRequest(`/api/missingness/events/${eventId}`, {
  method: 'PATCH',
  body: payload
})