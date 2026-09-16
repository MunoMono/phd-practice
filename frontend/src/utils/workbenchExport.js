export const downloadFile = (filename, content, mimeType = 'text/plain;charset=utf-8') => {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const escapeCsv = (value) => {
  const normalized = value === undefined || value === null ? '' : String(value)
  if (/[",\n]/.test(normalized)) {
    return `"${normalized.replace(/"/g, '""')}"`
  }
  return normalized
}

export const downloadCsv = (filename, rows) => {
  if (!rows || rows.length === 0) {
    downloadFile(filename, '', 'text/csv;charset=utf-8')
    return
  }

  const headers = Object.keys(rows[0])
  const lines = [headers.join(',')]

  rows.forEach((row) => {
    lines.push(headers.map((header) => escapeCsv(row[header])).join(','))
  })

  downloadFile(filename, `${lines.join('\n')}\n`, 'text/csv;charset=utf-8')
}

export const downloadJson = (filename, payload) => {
  downloadFile(filename, `${JSON.stringify(payload, null, 2)}\n`, 'application/json;charset=utf-8')
}
