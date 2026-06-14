import { useState } from 'react'
import { useOnboardingStore } from '../../../store/onboardingStore'
import { TextField } from '../../ui/TextField'
import { LabeledSlider } from '../../ui/LabeledSlider'
import { Segmented } from '../../ui/Segmented'
import { Whisper } from '../../ui/Whisper'
import { ComfortPicker } from '../../ui/ComfortPicker'
import { PrimaryButton } from '../../ui/buttons'

export function AboutYou({ onNext }) {
  const self = useOnboardingStore((s) => s.members.find((m) => m.isSelf))
  const addMember = useOnboardingStore((s) => s.addMember)
  const updateMember = useOnboardingStore((s) => s.updateMember)

  const [name, setName] = useState(self?.name ?? '')
  const [age, setAge] = useState(self?.age ?? 25)
  const [earns, setEarns] = useState(self?.earns ?? true)
  const [occupation, setOccupation] = useState(self?.occupation ?? '')
  const [moneyComfort, setMoneyComfort] = useState(self?.moneyComfort ?? null)

  const save = () => {
    const fields = {
      name: name.trim(),
      age,
      earns,
      occupation: earns ? occupation.trim() : '',
      moneyComfort,
      relationship: 'You',
      isSelf: true,
    }
    if (self) updateMember(self.id, fields)
    else addMember(fields)
    onNext()
  }

  return (
    <div className="mx-auto flex h-full max-w-md flex-col gap-6 overflow-y-auto px-5 py-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-[var(--color-ink)]">
          Let&apos;s start with you
        </h1>
        <Whisper>
          Your advisor builds everything around the people. The numbers come later.
        </Whisper>
      </div>

      <TextField
        label="Your name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="What should we call you?"
        autoFocus
      />

      <LabeledSlider label="Your age" value={age} min={16} max={90} onChange={setAge} />

      <div>
        <label className="text-sm font-medium text-[var(--color-ink)]">Do you earn?</label>
        <div className="mt-1.5">
          <Segmented
            options={[
              { value: true, label: 'I earn' },
              { value: false, label: 'Not right now' },
            ]}
            value={earns}
            onChange={setEarns}
          />
        </div>
        <Whisper>So the advisor knows whose income the family leans on.</Whisper>
      </div>

      {earns && (
        <TextField
          label="What do you do?"
          value={occupation}
          onChange={(e) => setOccupation(e.target.value)}
          placeholder="e.g. Software engineer, runs a shop…"
          whisper="The kind of work says a lot: how steady the income is, how it could grow."
        />
      )}

      <ComfortPicker
        label="How comfortable are you with money matters?"
        value={moneyComfort}
        onChange={setMoneyComfort}
      />

      <div className="mt-auto pb-2">
        <PrimaryButton disabled={!name.trim()} onClick={save}>
          Next: your family
        </PrimaryButton>
      </div>
    </div>
  )
}
