import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { MapPin, CheckCircle, AlertCircle } from 'lucide-react';
import { scanApi } from '../../services/api';

const GPS_OPTIONS = {
  enableHighAccuracy: true,  // force GPS chip — cell-tower fix is wrong for Nigerian networks
  timeout: 45000,            // 45 s — cold GPS start indoors can take 30+ s
  maximumAge: 0,             // always a fresh fix; cached desktop position is useless here
};

const MobileLocationHandoff = () => {
  const { sessionId } = useParams();
  const [phase, setPhase] = useState('idle'); // idle | locating | submitting | success | error
  const [errorMsg, setErrorMsg] = useState(null);

  const handleShareLocation = () => {
    setPhase('locating');
    setErrorMsg(null);

    if (!navigator.geolocation) {
      setPhase('error');
      setErrorMsg('Location services are not supported in this browser. Try Chrome or Safari.');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        setPhase('submitting');
        try {
          await scanApi.submitPhoneLocation(sessionId, {
            latitude:  pos.coords.latitude,
            longitude: pos.coords.longitude,
          });
          setPhase('success');
        } catch (err) {
          setPhase('error');
          setErrorMsg(err?.message || 'Could not send your location to the server. Please try again.');
        }
      },
      (err) => {
        const messages = {
          1: 'Location access is blocked. Tap the lock icon in your browser address bar → Site settings → Location → Allow, then tap Try Again.',
          2: 'Could not get a location fix. Move to an open area, make sure GPS is on, and try again.',
          3: 'Location timed out. Move to an open area and try again.',
        };
        setPhase('error');
        setErrorMsg(messages[err.code] ?? 'Could not get your location. Please try again.');
      },
      GPS_OPTIONS,
    );
  };

  return (
    <div className="min-h-screen bg-black flex flex-col items-center justify-center px-6 py-10">
      <div className="w-full max-w-sm">

        {/* ── Header ── */}
        <div className="text-center mb-10">
          <p className="text-white/40 text-[10px] tracking-widest uppercase mb-2">SabiLens AI</p>
          <h1 className="text-white text-2xl font-bold leading-tight">Location Verification</h1>
        </div>

        {/* ── Idle ── */}
        {phase === 'idle' && (
          <>
            <div className="flex justify-center mb-8">
              <div className="w-24 h-24 rounded-full bg-green-500/15 border border-green-500/30 flex items-center justify-center">
                <MapPin size={44} className="text-green-400" />
              </div>
            </div>
            <p className="text-white/70 text-sm text-center leading-relaxed mb-8">
              Please verify your exact location to complete the product scan on your desktop computer.
            </p>
            <button
              onClick={handleShareLocation}
              className="w-full py-4 rounded-2xl bg-green-500 text-white font-bold text-base hover:bg-green-600 active:scale-95 transition-all"
            >
              Share My Location
            </button>
          </>
        )}

        {/* ── Locating / Submitting ── */}
        {(phase === 'locating' || phase === 'submitting') && (
          <div className="flex flex-col items-center gap-6 py-6">
            <div className="w-24 h-24 rounded-full bg-green-500/15 flex items-center justify-center">
              <div className="w-12 h-12 border-[3px] border-green-500 border-t-transparent rounded-full animate-spin" />
            </div>
            <div className="text-center">
              <p className="text-white font-semibold text-base mb-1">
                {phase === 'locating' ? 'Getting your location…' : 'Sending to desktop…'}
              </p>
              <p className="text-white/50 text-sm">
                {phase === 'locating' ? 'This may take a few seconds.' : 'Almost done.'}
              </p>
            </div>
          </div>
        )}

        {/* ── Success ── */}
        {phase === 'success' && (
          <div className="flex flex-col items-center gap-6 py-6">
            <div className="w-24 h-24 rounded-full bg-green-500/20 border border-green-500/40 flex items-center justify-center">
              <CheckCircle size={52} className="text-green-400" />
            </div>
            <div className="text-center">
              <p className="text-white font-bold text-xl mb-2">Location Shared!</p>
              <p className="text-white/60 text-sm leading-relaxed">
                Your desktop is now ready to complete the scan.
              </p>
              <p className="text-white/60 text-sm mt-1">
                You can return to your computer.
              </p>
            </div>
            <div className="w-full bg-green-500/10 border border-green-500/30 rounded-2xl p-4 text-center">
              <p className="text-green-400 text-sm font-semibold">✓ GPS location verified</p>
            </div>
          </div>
        )}

        {/* ── Error ── */}
        {phase === 'error' && (
          <>
            <div className="flex justify-center mb-6">
              <div className="w-24 h-24 rounded-full bg-red-500/15 border border-red-500/30 flex items-center justify-center">
                <AlertCircle size={44} className="text-red-400" />
              </div>
            </div>
            <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-4 mb-6">
              <p className="text-red-300 text-sm text-center leading-relaxed">{errorMsg}</p>
            </div>
            <button
              onClick={handleShareLocation}
              className="w-full py-4 rounded-2xl bg-green-500 text-white font-bold text-base hover:bg-green-600 active:scale-95 transition-all"
            >
              Try Again
            </button>
          </>
        )}

      </div>
    </div>
  );
};

export default MobileLocationHandoff;
