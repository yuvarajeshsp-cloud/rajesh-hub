import * as React from "react"
import { ChevronDown, X } from "lucide-react"
import { cn } from "../lib/utils"
import { Button } from "./ui/button"
import { Checkbox } from "./ui/checkbox"
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "./ui/command"

export interface MultiSelectOption {
  value: string
  label: string
}

export function MultiSelectFilter({
  label,
  options,
  selected,
  onChange,
  className,
}: {
  label: string
  options: MultiSelectOption[]
  selected: Set<string>
  onChange: (next: Set<string>) => void
  className?: string
}) {
  const [open, setOpen] = React.useState(false)

  function toggle(value: string) {
    const next = new Set(selected)
    if (next.has(value)) next.delete(value)
    else next.add(value)
    onChange(next)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className={cn("justify-between gap-2", className)}>
          <span>
            {label}
            {selected.size > 0 && <span className="ml-1 text-muted-foreground">({selected.size})</span>}
          </span>
          <ChevronDown className="size-3.5 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[240px] p-0" align="start">
        <Command>
          <CommandInput placeholder={`Search ${label.toLowerCase()}...`} />
          <CommandList>
            <CommandEmpty>No results.</CommandEmpty>
            <CommandGroup>
              {options.map((opt) => (
                <CommandItem
                  key={opt.value}
                  value={opt.label}
                  onSelect={() => toggle(opt.value)}
                  className="gap-2"
                >
                  <Checkbox checked={selected.has(opt.value)} />
                  <span>{opt.label}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
          {selected.size > 0 && (
            <div className="border-t p-1">
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-center gap-1 text-xs"
                onClick={() => onChange(new Set())}
              >
                <X className="size-3" /> Clear filter
              </Button>
            </div>
          )}
        </Command>
      </PopoverContent>
    </Popover>
  )
}
