import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Sparkle, X } from '@phosphor-icons/react'
import { ENDPOINTS } from '../lib/api'
import { useChatStore } from '../store/chatStore'
import { useOnboardingStore } from '../store/onboardingStore'

// Soft nudge. If the active member hasn't finished onboarding, invite them to
// complete it. Shown until the member acts on it: dismissing or clicking Finish
// setup marks it seen for the rest of the browser session (sessionStorage), so a
// refresh keeps showing it until then but it never nags after they respond.
// Never blocks the chat. App remounts this per active member (keyed), so each
// member starts from a hidden state.
export function OnboardingNudge() {
  const activeMember = useChatStore((s) => s.activeMember)
  const openHub = useOnboardingStore((s) => s.openHub)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!activeMember) return
    const seenKey = `onboardingNudgeShown:${activeMember}`
    if (sessionStorage.getItem(seenKey)) return
    let cancelled = false
    fetch(ENDPOINTS.onboardingStatus, {
      headers: { 'X-Member-Id': activeMember },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled || !data || data.finished) return
        setVisible(true)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [activeMember])

  // Mark seen only when the member responds, so a refresh re-shows the nudge
  // until they actually act on it.
  function dismiss() {
    if (activeMember) {
      sessionStorage.setItem(`onboardingNudgeShown:${activeMember}`, '1')
    }
    setVisible(false)
  }

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ type: 'spring', stiffness: 320, damping: 30 }}
          className="flex items-center gap-3 border-b border-[var(--color-border)] bg-[var(--accent-soft)] px-4 py-2.5"
        >
          <Sparkle size={16} weight="fill" className="shrink-0 text-[var(--accent)]" />
          <span className="min-w-0 flex-1 text-[13px] text-[var(--color-ink)]">
            Finish setting up and I can give you advice that actually fits your family.
          </span>
          <button
            type="button"
            onClick={() => {
              dismiss()
              openHub()
            }}
            className="press-shrink shrink-0 rounded-full bg-[var(--accent)] px-3 py-1 text-[12px] font-semibold text-[var(--accent-ink)] transition-[filter] hover:brightness-105"
          >
            Finish setup
          </button>
          <button
            type="button"
            aria-label="Dismiss"
            onClick={dismiss}
            className="press-shrink shrink-0 text-[var(--color-ink-muted)] transition-colors hover:text-[var(--color-ink)]"
          >
            <X size={16} weight="bold" />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
