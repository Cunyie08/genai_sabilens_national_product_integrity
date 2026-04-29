import { useState, useEffect, useRef, useCallback } from 'react';
import { scanApi } from '../services/api';

const WS_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000')
  .replace(/^http/, 'ws');

/**
 * Creates a cross-device scan session for QR handoff.
 *
 * Flow: desktop calls createSession() → displays QR → phone opens mobile URL →
 * phone submits scan with session_id → WebSocket delivers result to desktop.
 *
 * Status values:
 *   idle     – not started
 *   creating – POST /session in-flight
 *   ready    – QR available, waiting for phone scan
 *   complete – result received; onResult has been called
 *   error    – session creation failed
 */
const useScanSession = ({ onResult }) => {
  const [sessionId,     setSessionId]     = useState(null);
  const [mobileUrl,     setMobileUrl]     = useState(null);
  const [sessionStatus, setSessionStatus] = useState('idle');

  const wsRef        = useRef(null);
  const mountedRef   = useRef(true);
  const completeRef  = useRef(false);
  const onResultRef  = useRef(onResult);

  useEffect(() => { onResultRef.current = onResult; }, [onResult]);

  useEffect(() => {
    mountedRef.current  = true;
    completeRef.current = false;
    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, []);

  const createSession = useCallback(async () => {
    if (!mountedRef.current) return;
    completeRef.current = false;
    setSessionStatus('creating');

    try {
      const res = await scanApi.createSession();
      const { session_id, mobile_url } = res.data;
      if (!mountedRef.current) return;

      setSessionId(session_id);
      setMobileUrl(mobile_url);
      setSessionStatus('ready');

      const ws = new WebSocket(`${WS_BASE}/api/v1/scan/session/${session_id}/ws`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'ping') return;
          completeRef.current = true;
          setSessionStatus('complete');
          onResultRef.current?.(data);
        } catch {}
      };

      ws.onerror = () => {
        if (mountedRef.current && !completeRef.current) setSessionStatus('error');
      };

      ws.onclose = (event) => {
        if (mountedRef.current && event.code !== 1000 && !completeRef.current) {
          setSessionStatus('error');
        }
      };
    } catch {
      if (mountedRef.current) setSessionStatus('error');
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { sessionId, mobileUrl, sessionStatus, createSession };
};

export default useScanSession;
