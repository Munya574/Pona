import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getConditions,
  createProfile,
  storeProfileId,
  getStoredProfileId,
} from '../api'

export default function Onboarding() {
  const navigate = useNavigate()
  const [conditions, setConditions] = useState([])
  const [selected, setSelected] = useState([])
  const [triggers, setTriggers] = useState({}) // condition -> comma-separated text
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (getStoredProfileId()) navigate('/scan', { replace: true })
  }, [navigate])

  useEffect(() => {
    getConditions().then(setConditions).catch((e) => setError(e.message))
  }, [])

  const toggle = (name) =>
    setSelected((s) =>
      s.includes(name) ? s.filter((x) => x !== name) : [...s, name],
    )

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      // "coffee, tomato" -> one trigger row each, tagged with its condition
      const personal_triggers = Object.entries(triggers).flatMap(
        ([condition, text]) =>
          text
            .split(',')
            .map((t) => t.trim())
            .filter(Boolean)
            .map((ingredient) => ({ ingredient, condition })),
      )
      const profile = await createProfile({
        user_email: `local-${Date.now()}@pona.app`,
        profile_name: 'My Profile',
        sensitivities: selected,
        personal_triggers,
      })
      storeProfileId(profile.profile_id)
      navigate('/scan')
    } catch (e) {
      setError(e.message)
      setSaving(false)
    }
  }

  return (
    <div className="p-6 pb-32">
      <h1 className="text-2xl font-bold mt-10">What should Pona look for?</h1>
      <p className="text-gray-600 mt-2 text-sm leading-relaxed">
        Pick what applies to you. Pona checks ingredient labels against this
        list and tells you what it finds. It doesn&apos;t rate food, and it
        won&apos;t tell you what to eat.
      </p>

      {error && (
        <div className="mt-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm">
          {error}
        </div>
      )}

      <div className="mt-6 space-y-2">
        {conditions.map((c) => {
          const on = selected.includes(c.name)
          return (
            <div
              key={c.name}
              className={`rounded-xl border transition-colors ${
                on ? 'border-gray-900 bg-gray-50' : 'border-gray-200'
              }`}
            >
              <button
                onClick={() => toggle(c.name)}
                className="w-full text-left p-4 flex items-start gap-3"
              >
                <span
                  className={`mt-0.5 w-5 h-5 rounded border flex-shrink-0 flex items-center justify-center text-xs ${
                    on
                      ? 'bg-gray-900 border-gray-900 text-white'
                      : 'border-gray-300'
                  }`}
                >
                  {on && '✓'}
                </span>
                <span className="min-w-0">
                  <span className="font-medium block">{c.name}</span>
                  {c.note && (
                    <span className="text-xs text-gray-500 block mt-1 leading-relaxed">
                      {c.note}
                    </span>
                  )}
                </span>
              </button>

              {/* Conditions where triggers are individual get no assumed
                  list, so ask for the user's own. */}
              {on && c.user_defined && (
                <div className="px-4 pb-4">
                  <label className="text-xs text-gray-600 block mb-1">
                    Foods you react to (comma separated)
                  </label>
                  <input
                    type="text"
                    placeholder="coffee, tomato"
                    value={triggers[c.name] || ''}
                    onChange={(e) =>
                      setTriggers((t) => ({ ...t, [c.name]: e.target.value }))
                    }
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm"
                  />
                  <p className="text-xs text-gray-500 mt-1.5 leading-relaxed">
                    Without this, Pona has nothing to look for and will say so
                    rather than reporting all clear.
                  </p>
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="fixed bottom-0 left-0 right-0 max-w-md mx-auto p-6 bg-white border-t">
        <button
          onClick={handleSave}
          disabled={selected.length === 0 || saving}
          className="w-full py-3.5 rounded-xl bg-gray-900 text-white font-medium disabled:opacity-30"
        >
          {saving ? 'Saving…' : 'Continue'}
        </button>
      </div>
    </div>
  )
}
