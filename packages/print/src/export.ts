import * as XLSX from "xlsx"

export interface ExportField<T> {
  key: string
  label: string
  value: (row: T) => string | number | boolean | null
}

export function exportToExcel<T>(
  filename: string,
  sheetName: string,
  rows: T[],
  fields: ExportField<T>[],
) {
  const data = rows.map((row) => {
    const record: Record<string, string | number | boolean | null> = {}
    for (const field of fields) {
      record[field.label] = field.value(row)
    }
    return record
  })

  const worksheet = XLSX.utils.json_to_sheet(data)
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, sheetName)
  XLSX.writeFile(workbook, filename.endsWith(".xlsx") ? filename : `${filename}.xlsx`)
}
