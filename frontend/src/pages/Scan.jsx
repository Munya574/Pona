import { useEffect, useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  checkFood,
  getStoredProfileId,
  getCapabilities,
  readLabelPhoto,
} from '../api'

export default function Scan() {
  const navigate = useNavigate()
  const fileRef = useRef(null)

  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [reading, setReading] = useState(false)
  const [error, setError] = useState(null)
  const [caps, setCaps] = useState({ ocr: false })
  // Set when the text in the box came from a photo rather than being typed.
  const [ocr, setOcr] = useState(null)

  const profileId = getStoredProfileId()

  useEffect(() => {
    getCapabilities().then(setCaps).catch(() => setCaps({ ocr: false }))
  }, [])

  useEffect(() => {
    if (!profileId) navigate('/', { replace: true })
  }, [profileId, navigate])
  if (!profileId) return null

  async function handlePhoto(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setReading(true)
    setError(null)
    setOcr(null)
    try {
      const result = await readLabelPhoto(file)
      setText(result.text)
      setOcr(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setReading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleCheck() {
    setLoading(true)
    setError(null)
    try {
      const result = await checkFood(profileId, [text])
      navigate('/result', {
        state: {
          result,
          input: text,
          // Carried through so the result screen can say the text came
          // from a read that may have holes in it.
          ocrWarning: ocr && !ocr.reliable ? ocr : null,
        },
      })
    } catch (e) {
      setError(e.message)
      setLoading(false)
    }
  }

  return (
    <div className="p-6 flex flex-col min-h-screen">
      <div className="flex items-center justify-between mt-10">
        <h1 className="text-2xl font-bold">Check a food</h1>
        <div className="flex gap-4">
          <Link to="/card" className="text-sm text-gray-500 underline">
            Chef card
          </Link>
          <Link to="/profile" className="text-sm text-gray-500 underline">
            Profile
          </Link>
        </div>
      </div>

      <p className="text-gray-600 mt-2 text-sm leading-relaxed">
        Paste the ingredients from the label, brackets and all — Pona reads
        nested lists and &ldquo;may contain&rdquo; warnings.
      </p>

      {/* Only offered when the server can actually do it. A camera button
          that cannot work is worse than no camera button. */}
      {caps.ocr && (
        <>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={handlePhoto}
            className="hidden"
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={reading}
            className="mt-4 w-full py-3 rounded-xl border-2 border-gray-900 font-medium disabled:opacity-40"
          >
            {reading ? 'Reading label…' : 'Photograph the label'}
          </button>
        </>
      )}

      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setOcr(null) // edited by hand; the OCR caveat no longer applies
        }}
        placeholder="INGREDIENTS: MILK CHOCOLATE (SUGAR, COCOA BUTTER, MILK), PEANUTS, SALT. May contain traces of tree nuts."
        className="mt-4 w-full h-48 p-4 rounded-xl border border-gray-300 text-sm leading-relaxed resize-none focus:outline-none focus:border-gray-900"
      />

      {/* The review step. OCR drops words silently, so the person holding
          the packet checks the text before anything is matched. */}
      {ocr && (
        <div
          className={`mt-3 rounded-xl p-4 ${
            ocr.reliable
              ? 'bg-gray-50 border border-gray-200'
              : 'bg-amber-50 border border-amber-300'
          }`}
        >
          <p className="text-sm font-semibold">
            {ocr.reliable
              ? 'Check this matches the packet'
              : "This photo didn't read clearly"}
          </p>
          <p className="text-sm text-gray-700 mt-1 leading-relaxed">
            {ocr.reliable
              ? `Read ${ocr.word_count} words. Fix anything that came out wrong before checking — missing words mean missed ingredients.`
              : 'Words are probably missing, so a clean result would not mean much. Retake the photo, or type the ingredients yourself.'}
          </p>
          {ocr.warnings?.length > 0 && (
            <ul className="mt-2 space-y-1">
              {ocr.warnings.map((w, i) => (
                <li key={i} className="text-xs text-gray-600 leading-relaxed">
                  • {w}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {error && (
        <div className="mt-3 p-3 rounded-lg bg-red-50 text-red-700 text-sm leading-relaxed whitespace-pre-line">
          {error}
        </div>
      )}

      <button
        onClick={handleCheck}
        disabled={!text.trim() || loading}
        className="mt-4 w-full py-3.5 rounded-xl bg-gray-900 text-white font-medium disabled:opacity-30"
      >
        {loading ? 'Checking…' : 'Check ingredients'}
      </button>

      {!caps.ocr && (
        <p className="text-xs text-gray-400 mt-6 leading-relaxed">
          Label photos need Tesseract installed on the server. Until then,
          paste the text — Pona can only see what you give it.
        </p>
      )}
    </div>
  )
}
