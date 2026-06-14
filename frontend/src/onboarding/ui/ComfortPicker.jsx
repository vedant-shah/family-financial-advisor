import { TapCard } from './TapCard'
import { Whisper } from './Whisper'

// Per-person money-comfort picker. The value feeds each member's profile
// (financial_literacy), so the advisor can pitch explanations at the right
// level for whoever it's talking to. Copy is person-neutral so it reads fine
// for both "you" and another family member.
const COMFORT_OPTIONS = [
  { value: 'starting', title: 'Just starting out', subtitle: 'Most of this is new' },
  { value: 'basics', title: 'Knows the basics', subtitle: 'SIPs and FDs, gets the gist' },
  { value: 'confident', title: 'Pretty confident', subtitle: 'Tracks investments themselves' },
]

export function ComfortPicker({ label, value, onChange }) {
  return (
    <div>
      <label className="text-sm font-medium text-[var(--color-ink)]">{label}</label>
      <div className="mt-2 flex flex-col gap-2">
        {COMFORT_OPTIONS.map((o) => (
          <TapCard
            key={o.value}
            title={o.title}
            subtitle={o.subtitle}
            selected={value === o.value}
            onClick={() => onChange(o.value)}
          />
        ))}
      </div>
      <Whisper>So the advisor pitches explanations at the right level.</Whisper>
    </div>
  )
}
