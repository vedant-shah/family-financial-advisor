import { useState } from 'react'
import { motion } from 'motion/react'
import {
  CaretRight,
  Check,
  LinkSimple,
  Plant,
  TreeStructure,
  WhatsappLogo,
  X,
} from '@phosphor-icons/react'
import { useOnboardingStore } from '../store/onboardingStore'
import { memberPastel } from './theme'
import { PrimaryButton, GhostButton } from './ui/buttons'

const MEMBER_PHASES = [
  ['goals', 'Goals', 'lavender'],
  ['money', 'Money', 'mint'],
  ['check', 'Gut check', 'butter'],
]

export function Hub() {
  const members = useOnboardingStore((s) => s.members)
  const whoDone = useOnboardingStore((s) => s.whoDone)
  const exitOnboarding = useOnboardingStore((s) => s.exitOnboarding)
  const openPhase = useOnboardingStore((s) => s.openPhase)

  if (!whoDone && members.length === 0) {
    return <FirstRun onStart={() => openPhase('who')} onLater={exitOnboarding} />
  }

  return (
    <div className="flex h-dvh flex-col bg-[var(--color-bg)]">
      <header className="flex shrink-0 items-center justify-between px-4 py-3">
        <button
          onClick={exitOnboarding}
          aria-label="Back to chat"
          className="press-shrink flex h-11 w-11 items-center justify-center rounded-full text-[var(--color-ink-muted)] transition-colors hover:text-[var(--color-ink)]"
        >
          <X size={20} weight="bold" />
        </button>
        <h1 className="text-[15px] font-semibold tracking-tight text-[var(--color-ink)]">
          Family setup
        </h1>
        <span className="w-11" />
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto px-4 pb-10">
        <div className="mx-auto max-w-xl">
          <button
            onClick={() => openPhase('who')}
            className="press-shrink flex w-full items-center gap-3.5 rounded-[24px] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-left"
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[var(--color-peach-soft)]">
              <TreeStructure size={22} weight="duotone" className="text-[var(--color-peach)]" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1.5 text-[15px] font-semibold text-[var(--color-ink)]">
                Family tree
                {whoDone && <Check size={14} weight="bold" className="text-[var(--color-mint)]" />}
              </span>
              <span className="block text-[13px] text-[var(--color-ink-muted)]">
                {members.length} {members.length === 1 ? 'person' : 'people'}, tap to edit
              </span>
            </span>
            <CaretRight size={16} weight="bold" className="shrink-0 text-[var(--color-ink-muted)]" />
          </button>

          <div className="mt-4 overflow-hidden rounded-[24px] border border-[var(--color-border)] bg-[var(--color-surface)]">
            <div className="divide-y divide-[var(--color-border)]">
              {members.map((m, i) => (
                <MemberRow key={m.id} member={m} index={i} />
              ))}
            </div>
          </div>

          <p className="mt-5 text-center text-xs leading-relaxed text-[var(--color-ink-muted)]">
            Preview build. Answers stay in this browser, nothing reaches your advisor yet.
          </p>
        </div>
      </main>
    </div>
  )
}

function FirstRun({ onStart, onLater }) {
  return (
    <div className="flex h-dvh flex-col items-center justify-center bg-[var(--color-bg)] px-6">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 260, damping: 24 }}
        className="w-full max-w-sm text-center"
      >
        <span className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-[22px] bg-[var(--color-mint-soft)]">
          <Plant size={34} weight="duotone" className="text-[var(--color-mint)]" />
        </span>
        <h1 className="text-[28px] font-bold leading-tight tracking-tight text-[var(--color-ink)]">
          Let&apos;s meet your family
        </h1>
        <p className="mt-3 text-[15px] leading-relaxed text-[var(--color-ink-muted)]">
          A few taps: who&apos;s who, what you&apos;re working toward, a rough money
          picture. About 5 minutes, and rough answers are perfectly fine.
        </p>
        <div className="mt-8 flex flex-col gap-2">
          <PrimaryButton onClick={onStart}>Build your family tree</PrimaryButton>
          <GhostButton onClick={onLater}>Maybe later</GhostButton>
        </div>
      </motion.div>
    </div>
  )
}

function MemberRow({ member, index }) {
  const progress = useOnboardingStore((s) => s.progress[member.id])
  const openPhase = useOnboardingStore((s) => s.openPhase)
  const pastel = memberPastel(index)

  const next = MEMBER_PHASES.find(([key]) => !progress?.[key])
  const doneCount = MEMBER_PHASES.filter(([key]) => progress?.[key]).length

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, type: 'spring', stiffness: 320, damping: 28 }}
      className="flex flex-col gap-3 px-4 py-4 sm:px-5"
    >
      <div className="flex items-center gap-3">
        <span
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-[15px] font-semibold"
          style={{ background: pastel.solid, color: pastel.ink }}
        >
          {member.name.charAt(0).toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[15px] font-semibold text-[var(--color-ink)]">
            {member.name}
          </div>
          <div className="text-[12px] text-[var(--color-ink-muted)]">
            {member.isSelf ? 'You' : member.relationship}
            {doneCount === 0 && next ? ', about 3 min' : ''}
          </div>
        </div>
        <ShareButtons member={member} />
      </div>

      <div className="flex items-center gap-2">
        <div className="flex flex-1 flex-wrap items-center gap-1.5">
          {MEMBER_PHASES.map(([key, label, pastelName]) => {
            const done = !!progress?.[key]
            return (
              <button
                key={key}
                onClick={() => openPhase(key, member.id)}
                className={
                  'press-shrink flex items-center gap-1 rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors ' +
                  (done
                    ? 'border-transparent'
                    : 'border-[var(--color-border)] text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]')
                }
                style={
                  done
                    ? {
                        background: `var(--color-${pastelName}-soft)`,
                        color: `var(--color-${pastelName})`,
                      }
                    : undefined
                }
              >
                {done && <Check size={12} weight="bold" />}
                {label}
              </button>
            )
          })}
        </div>
        {next ? (
          <button
            onClick={() => openPhase(next[0], member.id)}
            className="press-shrink flex shrink-0 items-center gap-1 rounded-full bg-[var(--color-mint)] px-3.5 py-1.5 text-[12px] font-semibold text-[var(--color-mint-ink)]"
          >
            {doneCount === 0 ? 'Start' : 'Continue'}
            <CaretRight size={12} weight="bold" />
          </button>
        ) : (
          <span className="flex shrink-0 items-center gap-1 text-[12px] font-medium text-[var(--color-mint)]">
            <Check size={12} weight="bold" />
            All set
          </span>
        )}
      </div>
    </motion.div>
  )
}

function ShareButtons({ member }) {
  const [copied, setCopied] = useState(false)
  const link = `${window.location.origin}${window.location.pathname}?onboard=${member.id}`

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard unavailable, the WhatsApp path still works */
    }
  }

  const wa = `https://wa.me/?text=${encodeURIComponent(
    `Add your bit to our family's money plan, takes about 3 minutes: ${link}`,
  )}`

  return (
    <div className="flex shrink-0 items-center gap-1">
      <button
        onClick={copy}
        aria-label={`Copy invite link for ${member.name}`}
        title="Copy link"
        className="press-shrink flex h-10 w-10 items-center justify-center rounded-xl text-[var(--color-ink-muted)] transition-colors hover:text-[var(--color-ink)]"
      >
        {copied ? (
          <Check size={17} weight="bold" className="text-[var(--color-mint)]" />
        ) : (
          <LinkSimple size={17} weight="bold" />
        )}
      </button>
      <a
        href={wa}
        target="_blank"
        rel="noreferrer"
        aria-label={`Share on WhatsApp for ${member.name}`}
        title="Share on WhatsApp"
        className="press-shrink flex h-10 w-10 items-center justify-center rounded-xl text-[var(--color-ink-muted)] transition-colors hover:text-[var(--color-ink)]"
      >
        <WhatsappLogo size={18} weight="bold" />
      </a>
    </div>
  )
}
