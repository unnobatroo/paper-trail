import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export type Option = { value: string; label: string }

/** A labelled dropdown over a list of options. */
export function SimpleSelect({
  value,
  onChange,
  options,
  label,
  className,
  disabled,
}: {
  value: string
  onChange: (value: string) => void
  options: Option[]
  /** The accessible name; there is no visible label. */
  label: string
  className?: string
  disabled?: boolean
}) {
  const items = Object.fromEntries(options.map((o) => [o.value, o.label]))
  return (
    <Select value={value} onValueChange={(v) => v !== null && onChange(String(v))} items={items} disabled={disabled}>
      <SelectTrigger aria-label={label} className={className}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
