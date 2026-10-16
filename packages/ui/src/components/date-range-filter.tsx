import { DATE_RANGE_PRESETS, type DateRangePreset } from "../lib/date-range"
import { Input } from "./ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select"

export function DateRangeFilter({
  preset,
  onPresetChange,
  customFrom,
  customTo,
  onCustomFromChange,
  onCustomToChange,
}: {
  preset: DateRangePreset
  onPresetChange: (preset: DateRangePreset) => void
  customFrom: string
  customTo: string
  onCustomFromChange: (value: string) => void
  onCustomToChange: (value: string) => void
}) {
  return (
    <>
      <Select value={preset} onValueChange={(v) => onPresetChange(v as DateRangePreset)}>
        <SelectTrigger className="w-full sm:w-[170px]"><SelectValue /></SelectTrigger>
        <SelectContent>
          {DATE_RANGE_PRESETS.map((p) => (
            <SelectItem key={p.key} value={p.key}>{p.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      {preset === "custom" && (
        <>
          <Input type="date" className="w-full sm:w-[190px]" value={customFrom} onChange={(e) => onCustomFromChange(e.target.value)} />
          <Input type="date" className="w-full sm:w-[190px]" value={customTo} onChange={(e) => onCustomToChange(e.target.value)} />
        </>
      )}
    </>
  )
}
