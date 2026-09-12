import { useEffect, useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { lookupBarcode, checkFood, getStoredProfileId } from '../api'

/**
 * Scan a barcode, then CONFIRM the product before checking it.
 *
 * The confirmation step is not ceremony. A lookup returns what a community
 * database recorded, possibly years ago, and manufacturers reformulate
 * without changing the barcode. One survey respondent described exactly
 * this failure:
 *
 *   "I pretty recently bought a food similar to one I'd had before...
 *    The previous time I ate the food, it was vegetarian, but this one
 *    was not. I didn't realize until I'd eaten it."
 *
 * So the product name, brand and record age are shown and the user says
 * yes before anything is matched. Skipping that would make Pona confidently
 * wrong about a packet it never saw.
 *
 * TWO DECODERS, ON PURPOSE
 *
 * Chrome and Android expose BarcodeDetector natively - it is faster and
 * costs no bundle. Safari and iOS do not, but they do support getUserMedia,
 * so ZXing decodes the same camera stream in JavaScript. Without the
 * fallback an iPhone user's only option is typing thirteen digits while
 * standing in a shop, which is bad enough that they would not use it.
 *
 * ZXing is imported dynamically rather than at the top of the file: it is
 * roughly 440kB, and a browser with the native detector must never pay for
 * a decoder it will not run. Even on iOS it only downloads when the user
 * actually starts the camera.
 */
export default function BarcodeScan() {
  const navigate = useNavigate()
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const loopRef = useRef(null)
  const zxingRef = useRef(null)

  const [supported, setSupported] = useState(null) // null = still checking
  const [scanning, setScanning] = useState(false)
  const [manual, setManual] = useState('')
  const [product, setProduct] = useState(null)
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)

  const profileId = getStoredProfileId()

  useEffect(() => {
    if (!profileId) navigate('/', { replace: true })
  }, [profileId, navigate])

  useEffect(() => {
    // Either decoder counts as supported; they differ in speed, not ability.
    setSupported('BarcodeDetector' in window ? 'native' : 'zxing')
    return () => stopCamera()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function stopCamera() {
    if (loopRef.current) {
      clearInterval(loopRef.current)
      loopRef.current = null
    }
    if (zxingRef.current) {
      try {
        zxingRef.current.stop()
      } catch {
        // Already stopped; nothing to clean up.
      }
      zxingRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    setScanning(false)
  }

  async function startCamera() {
    setError(null)
    setProduct(null)

    if ('BarcodeDetector' in window) {
      await startNative()
    } else {
      await startZxing()
    }
  }

  /** Chrome / Android. Decoding happens off the main thread. */
  async function startNative() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setScanning(true)

      const detector = new window.BarcodeDetector({
        formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e'],
      })

      loopRef.current = setInterval(async () => {
        if (!videoRef.current) return
        try {
          const codes = await detector.detect(videoRef.current)
          if (codes.length) {
            stopCamera()
            handleCode(codes[0].rawValue)
          }
        } catch {
          // A frame that cannot be decoded is normal, not an error.
        }
      }, 350)
    } catch (e) {
      cameraError(e)
    }
  }

  /**
   * Safari / iOS. ZXing drives the camera itself and calls back on every
   * decoded frame, so there is no polling loop to manage - just its own
   * controls object, which stopCamera() disposes.
   */
  async function startZxing() {
    try {
      setStatus('starting camera')
      const { BrowserMultiFormatReader } = await import('@zxing/browser')
      setStatus(null)
      const reader = new BrowserMultiFormatReader()
      setScanning(true)
      const controls = await reader.decodeFromVideoDevice(
        undefined,
        videoRef.current,
        (result) => {
          if (result) {
            stopCamera()
            handleCode(result.getText())
          }
          // Errors here are "no barcode in this frame", which is the
          // normal case while the user is still aiming.
        },
      )
      zxingRef.current = controls
    } catch (e) {
      setScanning(false)
      setStatus(null)
      cameraError(e)
    }
  }

  function cameraError(e) {
    setError(
      e && e.name === 'NotAllowedError'
        ? 'Camera access was blocked. Allow it in your browser settings, or type the number below.'
        : 'Could not open the camera. Type the barcode number instead.',
    )
  }

  async function handleCode(code) {
    setStatus('looking up')
    setError(null)
    try {
      const p = await lookupBarcode(code)
      setProduct(p)
      setStatus(null)
    } catch (e) {
      setStatus(null)
      setError(e.message)
    }
  }

  async function confirmAndCheck() {
    setStatus('checking')
    try {
      const result = await checkFood(profileId, [product.ingredients_text])
      navigate('/result', {
        state: { result, input: product.ingredients_text, product },
      })
    } catch (e) {
      setStatus(null)
      setError(e.message)
    }
  }

  return (
    <div className="p-6 flex flex-col min-h-screen">
      <div className="flex items-center justify-between mt-10">
        <h1 className="text-2xl font-bold">Scan a barcode</h1>
        <Link to="/scan" className="text-sm text-gray-500 underline">
          Back
        </Link>
      </div>

      {!product && (
        <>
          <p className="text-gray-600 mt-2 text-sm leading-relaxed">
            Point the camera at the barcode on the packet.
          </p>

          <div className="mt-4 rounded-xl overflow-hidden bg-black aspect-[4/3] relative">
            <video
              ref={videoRef}
              playsInline
              muted
              className="w-full h-full object-cover"
            />
            {!scanning && (
              <div className="absolute inset-0 flex items-center justify-center">
                <p className="text-white/60 text-sm">Camera off</p>
              </div>
            )}
          </div>

          <button
            onClick={scanning ? stopCamera : startCamera}
            className="mt-4 w-full py-3.5 rounded-xl bg-gray-900 text-white font-medium"
          >
            {scanning ? 'Stop' : 'Start camera'}
          </button>
          {supported === 'zxing' && !scanning && (
            <p className="mt-2 text-xs text-gray-500 leading-relaxed">
              Scanning in this browser is a little slower. Hold steady and fill
              the frame with the barcode.
            </p>
          )}

          <div className="mt-5">
            <label className="text-xs text-gray-600 block mb-1">
              Or type the number under the barcode
            </label>
            <div className="flex gap-2">
              <input
                inputMode="numeric"
                value={manual}
                onChange={(e) => setManual(e.target.value)}
                placeholder="5000159407236"
                className="flex-1 px-3 py-2.5 rounded-lg border border-gray-300 text-sm font-mono"
              />
              <button
                onClick={() => handleCode(manual)}
                disabled={manual.replace(/\D/g, '').length < 8}
                className="px-4 rounded-lg border-2 border-gray-900 font-medium text-sm disabled:opacity-30"
              >
                Look up
              </button>
            </div>
          </div>
        </>
      )}

      {status && <p className="mt-4 text-sm text-gray-500">{status}…</p>}

      {error && (
        <div className="mt-4 p-3 rounded-lg bg-amber-50 border border-amber-300">
          <p className="text-sm text-amber-900 leading-relaxed">{error}</p>
          <Link
            to="/scan"
            className="inline-block mt-2 text-sm font-medium text-amber-900 underline"
          >
            Photograph the label instead
          </Link>
        </div>
      )}

      {/* Confirmation. The user is holding the packet; the database is not. */}
      {product && (
        <div className="mt-5">
          <p className="text-xs font-bold tracking-widest text-gray-500 uppercase">
            Is this what you&apos;re holding?
          </p>
          <p className="text-2xl font-bold leading-tight mt-2">{product.name}</p>
          {product.brand && (
            <p className="text-sm text-gray-600">{product.brand}</p>
          )}

          {product.ingredients_text ? (
            <>
              <p className="text-sm text-gray-700 mt-4 leading-relaxed">
                {product.ingredients_text.slice(0, 260)}
                {product.ingredients_text.length > 260 ? '…' : ''}
              </p>
              <p className="text-xs text-gray-500 mt-3 leading-relaxed">
                From {product.source}
                {product.last_modified
                  ? `, last updated ${product.last_modified}`
                  : ''}
                . Recipes change without the barcode changing, so check this
                matches the packet.
              </p>
              <button
                onClick={confirmAndCheck}
                disabled={status === 'checking'}
                className="mt-4 w-full py-3.5 rounded-xl bg-gray-900 text-white font-medium disabled:opacity-40"
              >
                {status === 'checking' ? 'Checking…' : 'Yes, check this'}
              </button>
            </>
          ) : (
            <p className="text-sm text-amber-900 bg-amber-50 border border-amber-300 p-3 rounded-lg mt-4 leading-relaxed">
              {product.warning ||
                'No ingredient list on record for this product.'}
            </p>
          )}

          <div className="flex gap-4 mt-4">
            <button
              onClick={() => {
                setProduct(null)
                setManual('')
              }}
              className="text-sm text-gray-500 underline"
            >
              No, scan again
            </button>
            <Link to="/scan" className="text-sm text-gray-500 underline">
              Photograph the label
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
