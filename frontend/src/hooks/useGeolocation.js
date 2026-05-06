import { useState, useCallback, useEffect, useRef } from 'react';

/**
 * "Ask once" geolocation hook.
 *
 * Fires automatically on mount. No manual trigger needed.
 *
 * WHY enableHighAccuracy: true
 * Cell-tower triangulation (enableHighAccuracy:false) is inaccurate for
 * Nigerian networks. Google's/Apple's cell-tower database has poor calibration
 * for many states — towers in Ogun, Oyo, Rivers, etc. are frequently mapped to
 * Lagos, causing every user on those networks to appear as Lagos regardless of
 * their real location. enableHighAccuracy:true forces the GPS chip, which gives
 * satellite-accurate coordinates. The 5-min maximumAge cache means this is only
 * slow on the very first scan of the session; every subsequent scan is instant.
 *
 * Status values:
 *   idle     – not yet started
 *   fetching – GPS in progress
 *   ready    – locationData populated
 *   error    – GPS failed; locationData is null
 */

const GPS_OPTIONS = {
  enableHighAccuracy: true,   // MUST be true — false gives wrong Nigerian state via cell triangulation
  timeout: 15000,             // GPS cold-start can take ~10s; 15s gives enough headroom
  maximumAge: 300000,         // 5-min cache — repeat scans resolve instantly from cached fix
};

const useGeolocation = () => {
  const [locationData,      setLocationData]      = useState(null);
  const [locationStatus,    setLocationStatus]    = useState('idle');
  const [locationError,     setLocationError]     = useState(null);
  const [locationErrorCode, setLocationErrorCode] = useState(null);

  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // Only update state when the component is still mounted.
  // Prevents "Can't perform a React state update on an unmounted component"
  // when a 10-second GPS timeout resolves after the user navigates away.
  const safeSet = (fn) => { if (mountedRef.current) fn(); };

  const fetchLocation = useCallback(() => {
    safeSet(() => { setLocationStatus('fetching'); setLocationError(null); setLocationErrorCode(null); });

    if (!navigator.geolocation) {
      safeSet(() => {
        setLocationStatus('error');
        setLocationError('Location services are not supported in this browser. Try Chrome or Safari.');
      });
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        safeSet(() => {
          setLocationData({ latitude: pos.coords.latitude, longitude: pos.coords.longitude });
          setLocationStatus('ready');
          setLocationError(null);
        });
      },
      (err) => {
        const messages = {
          1: 'Location access is blocked. Tap 🔒 in your browser address bar → Site settings → Location → Allow, then tap "Try Again".',
          2: 'Your device could not get a location fix. Move to an open area, ensure GPS is on, and try again.',
          3: 'Location timed out. Move to an open area and try again.',
        };
        safeSet(() => {
          setLocationStatus('error');
          setLocationError(messages[err.code] ?? 'Could not retrieve your location. Please try again.');
          setLocationErrorCode(err.code ?? null);
        });
      },
      GPS_OPTIONS,
    );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-fetch on mount — mirrors how the camera permission is handled.
  useEffect(() => {
    fetchLocation();
  }, [fetchLocation]);

  return {
    locationData,       // { latitude, longitude } | null — use directly in scan payload
    locationStatus,     // 'idle' | 'fetching' | 'ready' | 'error'
    locationError,      // human-readable string | null
    locationErrorCode,  // 1=permission denied, 2=unavailable, 3=timeout, null=no error yet
    retryLocation: fetchLocation,
  };
};

export default useGeolocation;
