/** Rows to CSV text. Quotes fields that need it; keeps numbers as shown on screen. */
export function toCsv(rows: string[][]): string {
  const cell = (v: string) => (/[",\r\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v)
  return rows.map((r) => r.map(cell).join(',')).join('\r\n')
}

/** Every table inside `root` as CSV rows (a blank row between tables). */
export function tablesToRows(root: HTMLElement): string[][] {
  const rows: string[][] = []
  root.querySelectorAll('table').forEach((table, i) => {
    if (i > 0) rows.push([])
    table.querySelectorAll('tr').forEach((tr) => {
      rows.push(Array.from(tr.querySelectorAll('th,td')).map((c) => (c.textContent ?? '').replace(/\s+/g, ' ').trim()))
    })
  })
  return rows
}

/** Download as UTF-8 with a BOM, so Excel shows Arabic correctly. */
export function downloadCsv(filename: string, rows: string[][]) {
  const blob = new Blob(['﻿' + toCsv(rows)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
