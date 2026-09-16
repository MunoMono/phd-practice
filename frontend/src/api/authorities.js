import apiRequest from './client'

const sumCounts = (items = []) => items.reduce((total, item) => total + (Number(item.count) || 0), 0)

export const getAuthoritySummary = async () => {
  const payload = await apiRequest('/api/authorities/summary')
  const authorityTypes = payload?.authority_types || []

  return {
    count: payload?.count || authorityTypes.length,
    authorityTypes,
    totalRecords: sumCounts(authorityTypes),
    coreRecords: sumCounts(authorityTypes.filter((item) => item.category === 'core')),
    criticalRecords: sumCounts(authorityTypes.filter((item) => item.category === 'critical')),
  }
}