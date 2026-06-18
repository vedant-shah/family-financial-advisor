import { X } from '@phosphor-icons/react'
import { PHASES, useOnboardingStore } from '../store/onboardingStore'
import { PHASE_PASTEL, accentStyle } from './theme'
import { WhoPhase } from './phases/who/WhoPhase'
import { GoalsPhase } from './phases/goals/GoalsPhase'
import { MoneyPhase } from './phases/money/MoneyPhase'
import { CheckPhase } from './phases/check/CheckPhase'

const PHASE_LABELS = { who: 'Family', goals: 'Goals', money: 'Money', check: 'Gut check' }

export function PhaseFlow() {
  const activePhase = useOnboardingStore((s) => s.activePhase)
  const openHub = useOnboardingStore((s) => s.openHub)

  return (
    <div
      className="flex h-dvh flex-col bg-[var(--color-bg)]"
      style={accentStyle(PHASE_PASTEL[activePhase] ?? 'mint')}
    >
      <header className="grid shrink-0 grid-cols-[1fr_auto_1fr] items-center px-4 py-3">
        <button
          onClick={openHub}
          aria-label="Back to family hub"
          className="press-shrink flex h-11 w-11 items-center justify-center justify-self-start rounded-full text-[var(--color-ink-muted)] transition-colors hover:text-[var(--color-ink)]"
        >
          <X size={20} weight="bold" />
        </button>
        <ProgressDots active={activePhase} />
        <span />
      </header>
      <main className="min-h-0 flex-1 overflow-hidden">
        {activePhase === 'who' ? (
          <WhoPhase />
        ) : activePhase === 'goals' ? (
          <GoalsPhase />
        ) : activePhase === 'money' ? (
          <MoneyPhase />
        ) : (
          <CheckPhase />
        )}
      </main>
    </div>
  )
}

function ProgressDots({ active }) {
  const idx = PHASES.indexOf(active)
  return (
    <div className="flex items-center gap-2">
      {PHASES.map((p, i) => (
        <div
          key={p}
          aria-label={PHASE_LABELS[p]}
          className={
            'h-1.5 rounded-full transition-all duration-300 ' + (i === idx ? 'w-7' : 'w-1.5')
          }
          style={{
            background:
              i <= idx ? `var(--color-${PHASE_PASTEL[p]})` : 'var(--color-border)',
            opacity: i < idx ? 0.55 : 1,
          }}
        />
      ))}
      <span className="ml-1 text-[12px] font-medium text-[var(--color-ink-muted)]">
        {PHASE_LABELS[active]}
      </span>
    </div>
  )
}
