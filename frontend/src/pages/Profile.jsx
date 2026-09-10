import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  getConditions,
  getProfile,
  updateProfile,
  getStoredProfileId,
  clearStoredProfile,
} from '../api'

export default function Profile() {
  const navigate = useNavigate()
  const profileId = getStoredProfileId()

  const [conditions, setConditions] = useState([])
  const [selected, setSelected] = useState([])
  const [triggers, setTriggers] = useState({})
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!profileId) {
      navigate('/', { replace: true })
      return
    }
    Promise.all([getConditions(), getProfile(profileId)])
      .then(([all, mine]) => {
        setConditions(all)
        setSelected(mine.sensitivities)
        const grouped = {}
        for (const t of mine.personal_triggers || []) {
          const key = t.condition || ''
          grouped[key] = grouped[key] ? `${grouped[key]}, ${t.ingredient}` : t.ingredient
        }
        setTriggers(grouped)
      })
      .catch((e) => setError(e.message))
  }, [profileId, navigate])

  const toggle = (name) =>
    setSelected((s) =>
      s.includes(name) ? s.filter((x) => x !== name) : [...s, name],
    )

  async function handleSave() {
    setStatus('saving')
    setError(null)
    try {
      const personal_triggers = Object.entries(triggers).flatMap(
        ([condition, text]) =>
          String(text)
            .split(',')
            .map((t) => t.trim())
            .filter(Boolean)
            .map((ingredient) => ({ ingredient, condition })),
      )
      await updateProfile(profileId, {
        user_email: `local-${profileId}@pona.app`,
        profile_name: 'My Profile',
        sensitivities: selected,
        personal_triggers,
      })
      setStatus('saved')
      setTimeout(() => setStatus(null), 2000)
    } catch (e) {
      setError(e.message)
      setStatus(null)
    }
  }

  function handleReset() {
    clearStoredProfile()
    navigate('/', { replace: true })
  }

  return (
    <div className="p-6 pb-32">
      <div className="flex items-center justify-between mt-10">
        <h1 className="text-2xl font-bold">Your profile</h1>
        <Link to="/scan" className="text-sm text-gray-500 underline">
          Done
        </Link>
      </div>

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
              className={`rounded-xl border ${
                on ? 'border-gray-900 bg-gray-50' : 'border-gray-200'
              }`}
            >
              <button
                onClick={() => toggle(c.name)}
                className="w-full text-left p-4 flex items-start gap-3"
              >
                <span
                  className={`mt-0.5 w-5 h-5 rounded border flex-shrink-0 flex items-center justify-center text-xs ${
                    on ? 'bg-gray-900 border-gray-900 text-white' : 'border-gray-300'
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
                </div>
              )}
            </div>
          )
        })}
      </div>

      <button
        onClick={handleReset}
        className="mt-8 text-sm text-gray-400 underline"
      >
        Start over with a new profile
      </button>

      <div className="fixed bottom-0 left-0 right-0 max-w-md mx-auto p-6 bg-white border-t">
        <button
          onClick={handleSave}
          disabled={selected.length === 0 || status === 'saving'}
          className="w-full py-3.5 rounded-xl bg-gray-900 text-white font-medium disabled:opacity-30"
        >
          {status === 'saving' ? 'Saving…' : status === 'saved' ? 'Saved' : 'Save changes'}
        </button>
      </div>
    </div>
  )
}
