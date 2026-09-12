import { useLocation, useNavigate, Link } from 'react-router-dom'
import { useEffect } from 'react'

// Presentation for each finding. Deliberately descriptive: these name what
// Pona found in relation to YOUR profile, never whether the food is good.
// There is no "safe" state, because Pona checked one profile, not a diet.
const STATES = {
  no_triggers_found: {
    label: 'No triggers found',
    sub: 'Nothing on your profile appears in these ingredients.',
    bar: 'bg-clear',
    tint: 'bg-green-50',
  },
  possible_triggers: {
    label: 'Possible triggers',
    sub: 'Something here might affect you, but the label is not definite.',
    bar: 'bg-possible',
    tint: 'bg-amber-50',
  },
  contains_trigger: {
    label: 'Contains something you listed',
    sub: 'One or more ingredients on your profile are in this food.',
    bar: 'bg-present',
    tint: 'bg-red-50',
  },
}

export default function Result() {
  const navigate = useNavigate()
  const { state } = useLocation()
  const result = state?.result

  useEffect(() => {
    if (!result) navigate('/scan', { replace: true })
  }, [result, navigate])
  if (!result) return null

  const ocrWarning = state?.ocrWarning
  const product = state?.product
  const view = STATES[result.verdict] || STATES.possible_triggers
  const confirmed = result.triggers.filter((t) => t.confidence === 'confirmed')
  const possible = result.triggers.filter((t) => t.confidence === 'possible')
  const gaps = [
    ...(result.unchecked_sensitivities || []),
    ...(result.conditions_needing_setup || []),
  ]

  return (
    <div className="min-h-screen pb-28">
      <div className={`${view.bar} h-2`} />

      <div className="p-6">
        <div className={`${view.tint} rounded-2xl p-5`}>
          <h1 className="text-2xl font-bold">{view.label}</h1>
          <p className="text-sm text-gray-700 mt-1.5 leading-relaxed">
            {view.sub}
          </p>
        </div>

        {product && (
          <div className="mt-5 pb-4 border-b border-gray-200">
            <p className="text-xs font-bold tracking-widest text-gray-500 uppercase">
              Checked against
            </p>
            <p className="text-lg font-semibold leading-tight mt-1">
              {product.name}
            </p>
            <p className="text-xs text-gray-500 mt-1.5 leading-relaxed">
              Ingredients from {product.source}
              {product.last_modified ? `, last updated ${product.last_modified}` : ''}
              . Recipes change without the barcode changing.
            </p>
          </div>
        )}

        {/* An unreliable photo read outranks everything else on this screen.
            If words were dropped, "no triggers found" is meaningless — the
            matcher only ever saw part of the label. */}
        {ocrWarning && (
          <div className="mt-5 rounded-xl border-2 border-amber-400 bg-amber-50 p-4">
            <p className="text-sm font-semibold text-amber-900">
              Based on a photo that didn&apos;t read clearly
            </p>
            <p className="text-sm text-amber-900 mt-1.5 leading-relaxed">
              Pona only saw {ocrWarning.word_count} words at{' '}
              {Math.round(ocrWarning.confidence)}% confidence. Ingredients were
              probably missed, so this result does not rule anything out.
              Retake the photo or type the label to be sure.
            </p>
          </div>
        )}

        {/* Coverage gaps come FIRST. A short result must never be mistaken
            for a clean bill of health when something wasn't checked. */}
        {gaps.length > 0 && (
          <div className="mt-5 rounded-xl border border-amber-300 bg-amber-50 p-4">
            <p className="text-sm font-semibold text-amber-900">
              This result doesn&apos;t cover everything
            </p>
            <p className="text-sm text-amber-900 mt-1.5 leading-relaxed whitespace-pre-line">
              {result.explanation.split('Note:')[1]?.trim() ||
                `Not checked: ${gaps.join(', ')}`}
            </p>
            {(result.conditions_needing_setup || []).length > 0 && (
              <Link
                to="/profile"
                className="inline-block mt-3 text-sm font-medium text-amber-900 underline"
              >
                Add your triggers
              </Link>
            )}
          </div>
        )}

        {confirmed.length > 0 && (
          <section className="mt-6">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Found in the ingredients
            </h2>
            <div className="mt-2 space-y-2">
              {confirmed.map((t, i) => (
                <div key={i} className="rounded-xl border border-gray-200 p-4">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-medium">{t.ingredient}</span>
                    <span className="text-xs text-gray-500 flex-shrink-0">
                      {t.sensitivity}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1.5 leading-relaxed">
                    {t.explanation}
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

        {possible.length > 0 && (
          <section className="mt-6">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Possible, not certain
            </h2>
            <div className="mt-2 space-y-2">
              {possible.map((t, i) => (
                <div
                  key={i}
                  className="rounded-xl border border-dashed border-gray-300 p-4"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-medium">{t.ingredient}</span>
                    <span className="text-xs text-gray-500 flex-shrink-0">
                      {t.sensitivity}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1.5 leading-relaxed">
                    {t.explanation}
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

        <details className="mt-6">
          <summary className="text-xs text-gray-500 cursor-pointer">
            What Pona read from your text
          </summary>
          <p className="text-xs text-gray-500 mt-2 leading-relaxed">
            {result.normalized_ingredients.join(' · ')}
          </p>
        </details>

        <p className="text-xs text-gray-400 mt-6 leading-relaxed">
          Pona reads labels; it can be wrong, and labels change. If a reaction
          is serious, check the packaging yourself.
        </p>
      </div>

      <div className="fixed bottom-0 left-0 right-0 max-w-md mx-auto p-6 bg-white border-t">
        <button
          onClick={() => navigate('/scan')}
          className="w-full py-3.5 rounded-xl bg-gray-900 text-white font-medium"
        >
          Check another
        </button>
      </div>
    </div>
  )
}
