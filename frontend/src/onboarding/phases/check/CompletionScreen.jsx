import { useEffect } from 'react'
import { motion } from 'motion/react'
import { Check, Coins, Confetti, Scales, Target } from '@phosphor-icons/react'
import { ENDPOINTS } from '../../../lib/api'
import { useOnboardingStore } from '../../../store/onboardingStore'
import { PrimaryButton } from '../../ui/buttons'

const NO_GOALS = []

// The payoff: what the advisor now knows about this member, and who is next.
export function CompletionScreen({ member }) {
  const goals = useOnboardingStore((s) => s.goals[member.id]) ?? NO_GOALS
  const progress = useOnboardingStore((s) => s.progress)
  const members = useOnboardingStore((s) => s.members)
  const openHub = useOnboardingStore((s) => s.openHub)
  const persistMemberData = useOnboardingStore((s) => s.persistMemberData)

  // Reaching this screen means the member finished their flow. Record it on the
  // backend so the chat stops nudging them. A member not yet in the backend
  // roster (created in the tree, not yet persisted) returns 400, which we
  // ignore until the data milestone creates member dirs.
  useEffect(() => {
    // Save this member's money/goals slice, then record completion so the chat
    // stops nudging them. Both are best-effort.
    persistMemberData(member.id)
    fetch(ENDPOINTS.onboardingComplete, {
      method: 'POST',
      headers: { 'X-Member-Id': member.id },
    }).catch(() => {})
  }, [member.id, persistMemberData])

  const nextMember = members.find(
    (m) =>
      m.id !== member.id &&
      !(progress[m.id]?.goals && progress[m.id]?.money && progress[m.id]?.check),
  )

  const rows = [
    {
      key: 'goals',
      Icon: Target,
      pastel: 'lavender',
      done: !!progress[member.id]?.goals,
      text:
        goals.length > 0
          ? `${goals.length} ${goals.length === 1 ? 'goal' : 'goals'} noted`
          : 'Goals',
    },
    {
      key: 'money',
      Icon: Coins,
      pastel: 'mint',
      done: !!progress[member.id]?.money,
      text: 'The money picture',
    },
    {
      key: 'check',
      Icon: Scales,
      pastel: 'butter',
      done: true,
      text: 'How the ups and downs feel',
    },
  ]

  return (
    <div className="flex h-full flex-col items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <motion.span
          initial={{ scale: 0.6, opacity: 0, rotate: -12 }}
          animate={{ scale: 1, opacity: 1, rotate: 0 }}
          transition={{ type: 'spring', stiffness: 260, damping: 18 }}
          className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-[22px] bg-[var(--accent-soft)]"
        >
          <Confetti size={34} weight="duotone" className="text-[var(--accent)]" />
        </motion.span>

        <h1 className="text-center text-[26px] font-bold leading-tight tracking-tight text-[var(--color-ink)]">
          {member.isSelf ? "That's you done" : `That's ${member.name} done`}
        </h1>
        <p className="mt-2 text-center text-[14px] leading-relaxed text-[var(--color-ink-muted)]">
          Here is what your advisor now has to work with:
        </p>

        <div className="mt-6 flex flex-col gap-2">
          {rows.map((row, i) => (
            <motion.div
              key={row.key}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: row.done ? 1 : 0.55, y: 0 }}
              transition={{ delay: 0.15 + i * 0.1, type: 'spring', stiffness: 320, damping: 28 }}
              className="flex items-center gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3.5"
            >
              <span
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
                style={{ background: `var(--color-${row.pastel}-soft)` }}
              >
                <row.Icon
                  size={18}
                  weight="duotone"
                  style={{ color: `var(--color-${row.pastel})` }}
                />
              </span>
              <span className="min-w-0 flex-1 text-[14px] font-medium text-[var(--color-ink)]">
                {row.text}
              </span>
              {row.done ? (
                <Check size={16} weight="bold" className="shrink-0 text-[var(--color-mint)]" />
              ) : (
                <span className="shrink-0 text-[12px] text-[var(--color-ink-muted)]">later</span>
              )}
            </motion.div>
          ))}
        </div>

        <p className="mt-5 text-center text-[13px] text-[var(--color-ink-muted)]">
          {nextMember
            ? `Next up: ${nextMember.name}. Anyone can fill their part, anytime.`
            : 'The whole family picture is in. Lovely work.'}
        </p>

        <PrimaryButton className="mt-4 w-full" onClick={openHub}>
          Back to family
        </PrimaryButton>
      </div>
    </div>
  )
}
