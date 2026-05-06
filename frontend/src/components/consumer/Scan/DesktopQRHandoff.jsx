import React, { useEffect } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import useScanSession from '../../../hooks/useScanSession';

/**
 * Full-screen overlay shown on desktop when GPS is unavailable.
 * Creates a scan session, shows a QR code, and waits for the phone
 * to complete the scan via WebSocket.
 *
 * Props:
 *   onResult(data) — called with the scan result payload when the phone finishes
 *   onClose()      — called when the user dismisses the overlay manually
 */
const DesktopQRHandoff = ({ onResult, onClose }) => {
  const { mobileUrl, sessionStatus, createSession } = useScanSession({ onResult });

  useEffect(() => {
    createSession();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="absolute inset-0 z-50 bg-black/95 backdrop-blur-md flex items-center justify-center px-6">
      <div className="bg-white rounded-2xl p-8 w-full max-w-sm relative">

        {/* Dismiss button — hidden once scan is complete */}
        {sessionStatus !== 'complete' && onClose && (
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 text-xl leading-none"
            aria-label="Close"
          >
            ×
          </button>
        )}

        {/* ── Creating session ── */}
        {sessionStatus === 'creating' && (
          <div className="flex flex-col items-center py-10 gap-4">
            <div className="w-8 h-8 border-4 border-green-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-gray-500 text-sm">Generating QR code…</p>
          </div>
        )}

        {/* ── QR ready ── */}
        {sessionStatus === 'ready' && mobileUrl && (
          <>
            <div className="text-center mb-6">
              <h2 className="text-xl font-bold text-gray-900 mb-2">Scan on your phone</h2>
              <p className="text-gray-500 text-sm leading-relaxed">
                Your computer doesn't have GPS. Scan this QR code with your phone to verify the product.
              </p>
            </div>

            <div className="flex justify-center mb-5">
              <div className="p-3 border-2 border-gray-200 rounded-xl">
                <QRCodeSVG value={mobileUrl} size={180} />
              </div>
            </div>

            <div className="bg-gray-50 rounded-xl p-3 mb-4 flex flex-col items-center gap-2">
              <p className="text-xs text-gray-500">Waiting for phone scan…</p>
              <div className="flex gap-1">
                {[0, 150, 300].map((delay) => (
                  <div
                    key={delay}
                    className="w-1.5 h-1.5 bg-green-500 rounded-full animate-bounce"
                    style={{ animationDelay: `${delay}ms` }}
                  />
                ))}
              </div>
            </div>

            <p className="text-xs text-gray-400 text-center">QR code expires in 5 minutes</p>
          </>
        )}

        {/* ── Result received ── */}
        {sessionStatus === 'complete' && (
          <div className="flex flex-col items-center py-10 gap-4">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
              <span className="text-green-600 text-3xl">✓</span>
            </div>
            <p className="text-gray-800 font-semibold">Scan received!</p>
            <p className="text-gray-500 text-sm">Loading results…</p>
          </div>
        )}

        {/* ── Error ── */}
        {sessionStatus === 'error' && (
          <div className="flex flex-col items-center py-10 gap-4">
            <p className="text-red-500 text-sm text-center">
              Could not create a scan session. Please check your connection and try again.
            </p>
            <button
              onClick={createSession}
              className="px-5 py-2 rounded-lg bg-green-500 text-white text-sm font-medium"
            >
              Try Again
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default DesktopQRHandoff;
