import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { getChefCard, getStoredProfileId } from '../api'

/**
 * Two audiences, one screen, deliberately separated.
 *
 * SHOW is handed to a server. They will read it for a few seconds, in bad
 * light, possibly not in their first language, while busy. So it carries
 * only what must not be in the food and how careful to be, at a size that
 * survives a glance. It fits without scrolling, because someone holding a
 * stranger's phone will not scroll it.
 *
 * ASK is separate so it does not bury what the kitchen must not miss - but
 * it is equally meant to be handed over. Asking out loud is precisely the
 * part the survey said was hard ("asking too many questions", "without
 * offending anyone"), and it is harder still for someone nonverbal or who
 * finds the exchange itself costly. So these are sized to be shown, not
 * just read, and phrased as questions a server can answer directly.
 */
export default function ChefCard() {
  const navigate = useNavigate()
  const [card, setCard] = useState(null)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('show')
  const [detail, setDetail] = useState(false)

  const profileId = getStoredProfileId()

  useEffect(() => {
    if (!profileId) {
      navigate('/', { replace: true })
      return
    }
    getChefCard(profileId).then(setCard).catch((e) => setError(e.message))
  }, [profileId, navigate])

  if (error) {
    return (
      <div className="p-6 pt-14">
        <p className="text-red-700 text-sm">{error}</p>
      </div>
    )
  }
  if (!card) {
    return (
      <div className="p-6 pt-14">
        <p className="text-gray-500 text-sm">Loading…</p>
      </div>
    )
  }

  const strict = card.severe || []
  const mild = card.manageable || []
  const personal = card.personal || []
  const empty = !strict.length && !mild.length && !personal.length

  const autoimmuneOnly =
    strict.some((c) => c.nature === 'autoimmune') &&
    !strict.some((c) => c.nature === 'allergy')

  return (
    <div className="h-[100dvh] flex flex-col bg-white">
      <div className="flex border-b shrink-0">
        <button
          onClick={() => setTab('show')}
          className={
            tab === 'show'
              ? 'flex-1 py-3 text-sm font-medium border-b-2 border-gray-900'
              : 'flex-1 py-3 text-sm font-medium text-gray-400'
          }
        >
          Show to staff
        </button>
        <button
          onClick={() => setTab('ask')}
          className={
            tab === 'ask'
              ? 'flex-1 py-3 text-sm font-medium border-b-2 border-gray-900'
              : 'flex-1 py-3 text-sm font-medium text-gray-400'
          }
        >
          Ask or show
        </button>
        <Link to="/scan" className="px-4 py-3 text-sm text-gray-400 self-center">
          Done
        </Link>
      </div>

      {tab === 'show' ? (
        <div className="flex-1 flex flex-col min-h-0 p-5">
          {empty ? (
            <p className="text-gray-500 text-sm">
              Nothing on your profile yet. Add conditions and this card fills in.
            </p>
          ) : (
            <>
              <p className="text-xs font-bold tracking-widest text-gray-500 uppercase shrink-0">
                I cannot eat
              </p>

              <div className="mt-2 flex-1 min-h-0 overflow-y-auto">
                {strict.map((c) => (
                  <Block key={c.condition} item={c} strict detail={detail} />
                ))}
                {mild.map((c) => (
                  <Block key={c.condition} item={c} detail={detail} />
                ))}

                {personal.length > 0 && (
                  <div className="mb-4">
                    <p className="text-3xl leading-tight font-bold text-gray-700">
                      {personal.map((p) => p.ingredient).join(' · ')}
                    </p>
                    <p className="text-sm text-gray-600 mt-0.5">
                      Foods I personally react to
                    </p>
                  </div>
                )}
              </div>

              <div className="shrink-0 mt-4">
                {card.cross_contact && (
                  <div className="border-2 border-gray-900 p-3">
                    <p className="text-base font-semibold leading-snug">
                      Please use clean equipment, boards and utensils.
                    </p>
                    <p className="text-sm text-gray-700 mt-1 leading-snug">
                      {autoimmuneOnly
                        ? 'Even a trace does real damage, even though this is not an allergy.'
                        : 'Even a small amount can cause a serious reaction.'}
                    </p>
                  </div>
                )}

                <button
                  onClick={() => setDetail(!detail)}
                  className="mt-3 text-sm underline text-gray-500"
                >
                  {detail ? 'Hide other names' : 'Show other names for these'}
                </button>

                <p className="text-xs text-gray-400 leading-snug mt-2">
                  {card.disclaimer}
                </p>
              </div>
            </>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-5">
          <p className="text-xs font-bold tracking-widest text-gray-500 uppercase">
            Please could you check
          </p>
          <p className="text-sm text-gray-600 leading-relaxed mt-2">
            Ask these, or hand the phone over — they are written so staff can
            read and answer them directly.
          </p>
          <ul className="mt-5 space-y-4">
            {card.questions_to_ask.map((q, i) => (
              <li key={i} className="flex gap-3">
                <span className="text-gray-300 font-mono text-base pt-1.5">
                  {i + 1}
                </span>
                <span className="text-2xl leading-snug font-medium">{q}</span>
              </li>
            ))}
          </ul>
          {card.questions_to_ask.length > 0 ? (
            <p className="text-sm text-gray-500 mt-6 leading-snug">
              Thank you — it makes a real difference.
            </p>
          ) : (
            <p className="text-sm text-gray-500 mt-4">
              No specific questions for this profile yet. Add your conditions and
              they will appear here.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * One condition. The ingredient names are the message and carry the size;
 * the condition name is context underneath, in plain language rather than
 * clinical shorthand a server would have to decode.
 */
function Block({ item, strict, detail }) {
  if (!item.avoid || !item.avoid.length) return null

  let context
  if (item.nature === 'autoimmune') {
    context = 'Celiac disease — autoimmune, not an allergy'
  } else if (item.nature === 'allergy') {
    context = item.condition + ' — a serious allergy'
  } else {
    context = item.condition + ' — causes real discomfort, not an emergency'
  }

  return (
    <div className="mb-4">
      <p
        className={
          strict
            ? 'text-4xl leading-tight font-bold'
            : 'text-3xl leading-tight font-bold text-gray-700'
        }
      >
        {item.avoid.join(' · ')}
      </p>
      <p className="text-sm text-gray-600 mt-0.5">{context}</p>
      {detail && item.also_listed_as && item.also_listed_as.length > 0 && (
        <p className="text-sm text-gray-500 mt-1.5 leading-snug">
          Also appears as: {item.also_listed_as.join(', ')}
        </p>
      )}
    </div>
  )
}
