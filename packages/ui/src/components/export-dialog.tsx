import * as React from "react"
import { Download } from "lucide-react"
import { exportToExcel, type ExportField } from "@rajesh-hub/print"
import { Button } from "./ui/button"
import { Checkbox } from "./ui/checkbox"
import { Label } from "./ui/label"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "./ui/dialog"
import { toast } from "sonner"

export function ExportDialog<T>({
  open,
  onOpenChange,
  title,
  filename,
  sheetName,
  rows,
  fields,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  filename: string
  sheetName: string
  rows: T[]
  fields: ExportField<T>[]
}) {
  const [selected, setSelected] = React.useState<Set<string>>(
    () => new Set(fields.map((f) => f.key)),
  )

  React.useEffect(() => {
    if (open) setSelected(new Set(fields.map((f) => f.key)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function toggleAll() {
    setSelected(selected.size === fields.length ? new Set() : new Set(fields.map((f) => f.key)))
  }

  function handleExport() {
    if (selected.size === 0) {
      toast.error("Select at least one field")
      return
    }
    if (rows.length === 0) {
      toast.error("No rows to export")
      return
    }
    const chosenFields = fields.filter((f) => selected.has(f.key))
    exportToExcel(filename, sheetName, rows, chosenFields)
    toast.success(`Exported ${rows.length} row(s)`)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent fullPage={false}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Choose which fields to include. Exports {rows.length} row(s) matching the current filters.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3 py-2">
          <button
            type="button"
            onClick={toggleAll}
            className="self-start text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            {selected.size === fields.length ? "Deselect all" : "Select all"}
          </button>
          <div className="grid max-h-72 grid-cols-2 gap-x-4 gap-y-2 overflow-y-auto">
            {fields.map((f) => (
              <div key={f.key} className="flex items-center gap-2">
                <Checkbox
                  id={`export-field-${f.key}`}
                  checked={selected.has(f.key)}
                  onCheckedChange={() => toggle(f.key)}
                />
                <Label htmlFor={`export-field-${f.key}`} className="text-sm font-normal">
                  {f.label}
                </Label>
              </div>
            ))}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleExport}>
            <Download className="size-4" /> Export
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
