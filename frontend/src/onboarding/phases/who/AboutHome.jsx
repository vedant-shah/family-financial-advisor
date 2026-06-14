import { useState } from 'react'
import { ENDPOINTS } from '../../../lib/api'
import { useOnboardingStore } from '../../../store/onboardingStore'
import { useChatStore } from '../../../store/chatStore'
import { TextField } from '../../ui/TextField'
import { Whisper } from '../../ui/Whisper'
import { PrimaryButton } from '../../ui/buttons'

export function AboutHome() {
  const household = useOnboardingStore((s) => s.household)
  const setHousehold = useOnboardingStore((s) => s.setHousehold)
  const markWhoDone = useOnboardingStore((s) => s.markWhoDone)
  const persistRoster = useOnboardingStore((s) => s.persistRoster)
  const openHub = useOnboardingStore((s) => s.openHub)
  const setMembers = useChatStore((s) => s.setMembers)
  const setActiveMember = useChatStore((s) => s.setActiveMember)
  const resetForMemberSwitch = useChatStore((s) => s.resetForMemberSwitch)

  const [city, setCity] = useState(household.city ?? '')

  const finish = async () => {
    setHousehold({ city: city.trim() })
    markWhoDone()
    // Persist the roster, then point the app at the freshly created members.
    const result = await persistRoster()
    if (result?.self) {
      try {
        const { members } = await fetch(ENDPOINTS.members).then((r) => r.json())
        setMembers(members)
      } catch {
        /* picker refresh is best-effort; it reloads on next app start */
      }
      resetForMemberSwitch()
      setActiveMember(result.self)
    }
    openHub()
  }

  return (
    <div className="mx-auto flex h-full max-w-md flex-col gap-6 overflow-y-auto px-5 py-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-[var(--color-ink)]">
          A little about home
        </h1>
        <Whisper>One quick thing, totally optional.</Whisper>
      </div>

      <TextField
        label="Which city is home?"
        value={city}
        onChange={(e) => setCity(e.target.value)}
        placeholder="e.g. Mumbai"
        whisper="Costs and house prices differ a lot city to city. It keeps the advice realistic."
      />

      <div className="mt-auto pb-2">
        <PrimaryButton onClick={finish}>Finish family setup</PrimaryButton>
      </div>
    </div>
  )
}
