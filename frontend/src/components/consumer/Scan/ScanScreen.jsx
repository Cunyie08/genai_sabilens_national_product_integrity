import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { X, Image, ArrowRight, Check, AlertCircle, CameraOff, Flashlight } from 'lucide-react';
import { scanApi } from '../../../services/api';
import { saveScan } from '../../../services/scanHistory';
import useMediaPipeDetection from '../../../hooks/useMediaPipeDetection';

const TOTAL_PHASES = 2;

const scanPhases = [
  {
    id: 0,
    name: 'Front',
    instruction: 'Front label',
    description: 'Position the front label clearly in frame',
    target: 'Product name, brand logo, NAFDAC number',
    icon: 'Square',
    nextInstruction: 'Great! Now flip to the back panel',
    captureMessage: 'Front panel captured!',
    guideMessage: '📸 Scan the front panel containing the brand logo and product name',
    alignMessage: 'Align front packaging within the frame to scan',
    continueButtonText: 'Continue to Back Panel',
  },
  {
    id: 1,
    name: 'Back',
    instruction: 'Back label',
    description: 'Show the NAFDAC number, batch code and manufacturer details',
    target: 'NAFDAC number, batch code, expiry date, manufacturer',
    icon: 'RotateCcw',
    nextInstruction: 'Both sides captured! Sending to AI…',
    captureMessage: 'Back panel captured!',
    guideMessage: '🔍 Scan the back/side panel containing the NAFDAC number and batch code',
    alignMessage: 'Align back/side packaging within the frame to scan',
    continueButtonText: 'Submit to AI',
  },
];

const featuresByPhase = {
  0: ['✓ Brand detected', '✓ Logo region found', '✓ NAFDAC area located', '✓ Text extracted'],
  1: ['✓ NAFDAC number found', '✓ Batch code detected', '✓ Expiry date found', '✓ Manufacturer info'],
};

const emptyImages = { 0: null, 1: null };

const detectProductCategory = () => 'unknown';

const ScanScreen = () => {
  const navigate = useNavigate();

  // Camera state
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const [cameraPermission, setCameraPermission] = useState('idle');

  // Scan state
  const [scanning, setScanning] = useState(false);
  const [currentPhase, setCurrentPhase] = useState(0);
  const [completedPhases, setCompletedPhases] = useState([]);
  const [detectedFeatures, setDetectedFeatures] = useState([]);
  const [showSuccess, setShowSuccess] = useState(false);
  const [showNextPrompt, setShowNextPrompt] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [uploadMode, setUploadMode] = useState(false);
  const [uploadSlots, setUploadSlots] = useState({ 0: null, 1: null });
  const [torchOn, setTorchOn] = useState(false);
  const [showGuidancePhase, setShowGuidancePhase] = useState(true);
  const [waitingForContinue, setWaitingForContinue] = useState(false);
  const [scanProgress, setScanProgress] = useState(0);

  // Scanning line state
  const [linePosition, setLinePosition] = useState(0);
  const [scanDirection, setScanDirection] = useState('down');
  const scanLineRef = useRef(null);
  const captureTimerRef = useRef(null);

  // Refs
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const canvasRef = useRef(null);
  const fileInputRef = useRef(null);
  const uploadSlotRef = useRef(0);
  const capturedImagesRef = useRef({ ...emptyImages });
  const geoRef = useRef({ latitude: 0, longitude: 0, address: '' });
  const guidanceTimerRef = useRef(null);
  const alignTimerRef = useRef(null);

  // MediaPipe Detection Hook
  const {
    isProductDetected,
    detectionConfidence,
    detectionState,
    getDetailedFeedback,
    isModelLoading,
    resetTrigger
  } = useMediaPipeDetection(
    videoRef, 
    cameraActive && !scanning && !submitting && !showNextPrompt && !waitingForContinue,
    null
  );

  const detectionFeedback = getDetailedFeedback();

  // ── Error Messages ─────────────────────────────────────────────────────────
  const getUserFriendlyErrorMessage = (error) => {
    const message = error?.message?.toLowerCase() || '';
    const status = error?.status;
    if (!navigator.onLine || message.includes('network') || message.includes('fetch') || message.includes('failed to fetch')) return 'No internet connection. Please check your network and try again.';
    if (message.includes('timeout') || message.includes('timed out')) return 'Request timed out. Please check your connection and try again.';
    if (status === 500 || message.includes('internal server error')) return 'Our servers are experiencing issues. Please try again in a few minutes.';
    if (status === 503 || message.includes('unavailable')) return 'Service temporarily unavailable. Please try again later.';
    if (status === 429 || message.includes('too many')) return 'Too many scan requests. Please wait a moment before trying again.';
    if (message.includes('blurry') || message.includes('unclear') || message.includes('quality')) return 'The image is unclear. Please ensure the product is well-lit and the label is readable.';
    if (message.includes('nafdac') && (message.includes('not found') || message.includes('missing'))) return 'The NAFDAC number was not found. Please ensure the back/side label is clearly visible.';
    if (status === 401 || message.includes('unauthorized') || message.includes('token')) return 'Your session has expired. Please log in again to continue.';
    return 'Unable to analyze the product. Please try again with a clearer image.';
  };

  // ── Capture ────────────────────────────────────────────────────────────────
  const captureImage = useCallback((phaseIndex) => {
    if (!videoRef.current || !canvasRef.current) return null;
    const canvas = canvasRef.current;
    const video = videoRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
    capturedImagesRef.current = { ...capturedImagesRef.current, [phaseIndex]: dataUrl };
    return dataUrl;
  }, []);

  // ── Submit to AI ───────────────────────────────────────────────────────────
  const submitToAI = useCallback(async (images) => {
    setSubmitting(true);
    setSubmitError(null);
    const primaryImage = images[0];
    const backImage = images[1] || null;
    if (!primaryImage) { setSubmitError('No image captured. Please try again.'); setSubmitting(false); return; }
    const detectedCategory = detectProductCategory(primaryImage);
    const geo = geoRef.current;
    try {
      const payload = {
        image_data: primaryImage,
        back_image_data: backImage,
        category: detectedCategory,
        purchase_channel: 'unknown',
        latitude: geo.latitude,
        longitude: geo.longitude,
        location_text: geo.address || '',
      };
      const response = await scanApi.submitScan(payload);
      const data = response.data || {};
      const verdict = data.verdict || data.final_verdict || 'FAKE';
      
      const scanRecord = {
        id: data.scan_id || `scan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        product: data.product_name || 'Verified Product',
        productImage: primaryImage,
        status: verdict.toLowerCase(),
        category: detectedCategory,
        location: geo.address || '',
        latitude: geo.latitude,
        longitude: geo.longitude,
        similarity: data.confidence_score ? Math.round(data.confidence_score * 100) : null,
        timestamp: Date.now(),
        date: new Date().toISOString(),
        details: data
      };
      
      await saveScan(scanRecord);
      
      sessionStorage.setItem('currentScan', JSON.stringify({
        productImage: primaryImage,
        backImage,
        imageUrl: data.image_url || null,
        isAuthentic: verdict === 'AUTHENTIC',
        isSuspicious: verdict === 'SUSPICIOUS',
        isRescanRequired: verdict === 'RESCAN_REQUIRED',
        aiResult: data,
        location: geo.address || '',
        latitude: geo.latitude,
        longitude: geo.longitude,
        category: detectedCategory,
        scan_id: scanRecord.id
      }));
      
      if (verdict === 'AUTHENTIC') {
        navigate('/scan/safe');
      } else if (verdict === 'SUSPICIOUS') {
        navigate('/scan/suspicious');
      } else if (verdict === 'RESCAN_REQUIRED') {
        navigate('/scan/rescan');
      } else {
        navigate('/scan/fake');
      }
    } catch (err) {
      setSubmitError(getUserFriendlyErrorMessage(err));
      setSubmitting(false);
      setScanning(false);
    }
  }, [navigate]);

  // ── Guidance Message Management ───────────────────────────────────────────
  const startGuidance = useCallback((phaseIndex) => {
    if (guidanceTimerRef.current) clearTimeout(guidanceTimerRef.current);
    if (alignTimerRef.current) clearTimeout(alignTimerRef.current);
    
    setShowGuidancePhase(true);
    
    alignTimerRef.current = setTimeout(() => {
      setShowGuidancePhase(false);
    }, 5000);
  }, []);

  const clearGuidance = useCallback(() => {
    if (guidanceTimerRef.current) clearTimeout(guidanceTimerRef.current);
    if (alignTimerRef.current) clearTimeout(alignTimerRef.current);
    setShowGuidancePhase(true);
  }, []);

  // ── Complete phase capture ────────────────────────────────────────────────
  const completePhaseCapture = useCallback((phaseIndex) => {
    setCompletedPhases((prev) => [...prev, phaseIndex]);
    setDetectedFeatures((prev) => [...prev, ...(featuresByPhase[phaseIndex] || [])]);
    setShowSuccess(true);
    setScanning(false);
    setWaitingForContinue(true);
    resetTrigger();
    
    if (scanLineRef.current) { clearInterval(scanLineRef.current); scanLineRef.current = null; }
    if (captureTimerRef.current) { clearTimeout(captureTimerRef.current); captureTimerRef.current = null; }
    
    setTimeout(() => {
      setShowSuccess(false);
      if (phaseIndex === TOTAL_PHASES - 1) {
        // Back panel captured - auto-submit to AI
        submitToAI(capturedImagesRef.current);
      } else {
        setShowNextPrompt(true);
      }
    }, 800);
  }, [resetTrigger, submitToAI]);

  // ── Start scanning animation ───────────────────────────────────────────────
  const stopScan = useCallback(() => {
    if (scanLineRef.current) { clearInterval(scanLineRef.current); scanLineRef.current = null; }
    if (captureTimerRef.current) { clearTimeout(captureTimerRef.current); captureTimerRef.current = null; }
    setLinePosition(0);
    setScanDirection('down');
    setScanProgress(0);
    setScanning(false);
  }, []);

  const startScan = useCallback(() => {
    if (!cameraActive) { setCameraError('Please enable camera access to start scanning.'); return; }
    if (!detectionState.hasObject) { 
      setSubmitError('Please position a product in the frame before scanning.');
      return;
    }
    
    setScanning(true);
    setShowNextPrompt(false);
    setWaitingForContinue(false);
    setScanProgress(0);
    clearGuidance();
    
    // Start scanning line animation - moves down then up
    if (scanLineRef.current) clearInterval(scanLineRef.current);
    let pos = 0;
    let dir = 'down';
    setScanDirection('down');
    
    scanLineRef.current = setInterval(() => {
      if (dir === 'down') {
        pos = Math.min(pos + 2, 100);
        setScanProgress(pos);
        if (pos >= 100) {
          dir = 'up';
          setScanDirection('up');
        }
      } else {
        pos = Math.max(pos - 2, 0);
        setScanProgress(pos);
        if (pos <= 0) {
          // Scan complete - capture image
          clearInterval(scanLineRef.current);
          scanLineRef.current = null;
          captureImage(currentPhase);
          completePhaseCapture(currentPhase);
        }
      }
      setLinePosition(pos);
    }, 25);
  }, [cameraActive, detectionState.hasObject, currentPhase, captureImage, completePhaseCapture, clearGuidance]);

  // ── Camera ─────────────────────────────────────────────────────────────────
  const startCamera = useCallback(async () => {
    setCameraPermission('requesting');
    setCameraError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraPermission('unsupported');
      setCameraError('Your browser does not support camera access.');
      return;
    }
    try {
      if (streamRef.current) { streamRef.current.getTracks().forEach((t) => t.stop()); streamRef.current = null; }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) { stream.getTracks().forEach((t) => t.stop()); return; }
      video.srcObject = stream;
      await new Promise((resolve, reject) => { video.onloadedmetadata = resolve; video.onerror = reject; });
      await video.play();
      setCameraActive(true);
      setCameraPermission('granted');
    } catch (err) {
      streamRef.current = null;
      setCameraActive(false);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setCameraPermission('denied');
        setCameraError('Camera access was denied. Please allow camera access and tap Retry.');
      } else if (err.name === 'NotFoundError') {
        setCameraPermission('denied');
        setCameraError('No camera found on this device.');
      } else {
        setCameraPermission('denied');
        setCameraError(`Could not access the camera: ${err.message}`);
      }
    }
  }, []);

  const toggleTorch = useCallback(async () => {
    if (!streamRef.current) return;
    const track = streamRef.current.getVideoTracks()[0];
    if (!track) return;
    const newState = !torchOn;
    try {
      await track.applyConstraints({ advanced: [{ torch: newState }] });
      setTorchOn(newState);
    } catch (e) {
      console.warn('Torch not supported on this device');
    }
  }, [torchOn]);

  useEffect(() => {
    startCamera();
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lng = pos.coords.longitude;
          geoRef.current = { latitude: lat, longitude: lng, address: `${lat.toFixed(5)}° N, ${lng.toFixed(5)}° E` };
        },
        () => {},
        { enableHighAccuracy: true, timeout: 10000 },
      );
    }
    return () => {
      stopScan();
      clearGuidance();
      if (streamRef.current) { streamRef.current.getTracks().forEach((t) => t.stop()); streamRef.current = null; }
    };
  }, []);

  // Start guidance when camera is active and not scanning
  useEffect(() => {
    if (cameraActive && !scanning && !submitting && !showNextPrompt && !waitingForContinue) {
      startGuidance(currentPhase);
    } else {
      clearGuidance();
    }
    return () => clearGuidance();
  }, [cameraActive, scanning, submitting, showNextPrompt, waitingForContinue, currentPhase, startGuidance]);

  // ── Scan Controls ──────────────────────────────────────────────────────────
  const resetScan = useCallback(() => {
    stopScan();
    clearGuidance();
    setScanning(false);
    setCurrentPhase(0);
    setCompletedPhases([]);
    setDetectedFeatures([]);
    setShowSuccess(false);
    setShowNextPrompt(false);
    setWaitingForContinue(false);
    setSubmitting(false);
    setSubmitError(null);
    setLinePosition(0);
    setScanDirection('down');
    setScanProgress(0);
    capturedImagesRef.current = { ...emptyImages };
    if (cameraActive) {
      startGuidance(0);
    }
    resetTrigger();
  }, [stopScan, clearGuidance, cameraActive, startGuidance, resetTrigger]);

  const handleFileUpload = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    setSubmitError(null);
    const slot = uploadSlotRef.current;
    const reader = new FileReader();
    reader.onload = () => { setUploadSlots(prev => ({ ...prev, [slot]: reader.result })); };
    reader.readAsDataURL(file);
  }, []);

  const handleSubmitUploads = useCallback(() => {
    if (!uploadSlots[0] || !uploadSlots[1]) { setSubmitError('Please select both the front and back panel images before analysing.'); return; }
    const slots = { ...uploadSlots };
    setUploadSlots({ 0: null, 1: null });
    setUploadMode(false);
    submitToAI(slots);
  }, [uploadSlots, submitToAI]);

  const openSlotPicker = useCallback((slotIndex) => {
    uploadSlotRef.current = slotIndex;
    fileInputRef.current?.click();
  }, []);

  const continueToNextPhase = useCallback(() => {
    setShowNextPrompt(false);
    setWaitingForContinue(false);
    const nextPhase = currentPhase + 1;
    setCurrentPhase(nextPhase);
    startGuidance(nextPhase);
    resetTrigger();
  }, [currentPhase, startGuidance, resetTrigger]);

  const currentPhaseData = scanPhases[currentPhase] ?? scanPhases[0];

  // Scan button is green when product is detected
  const canStartScan = cameraActive && detectionState.hasObject && !scanning && !submitting && !showNextPrompt && !waitingForContinue && !isModelLoading;

  // Get current guidance message
  const getGuidanceMessage = () => {
    if (showGuidancePhase) {
      return currentPhaseData.guideMessage;
    }
    return currentPhaseData.alignMessage;
  };

  // Get hint message
  const getHintMessage = () => {
    if (submitError) return submitError;
    if (submitting) return 'SabiLens AI is analysing…';
    if (showNextPrompt && waitingForContinue) {
      return `${currentPhaseData.captureMessage} ${currentPhaseData.nextInstruction}`;
    }
    if (scanning) {
      if (scanDirection === 'down') {
        return `Scanning ${currentPhaseData.name} panel — moving down`;
      }
      return `Scanning ${currentPhaseData.name} panel — moving up`;
    }
    if (!scanning && !showNextPrompt && !waitingForContinue) {
      if (!detectionState.hasObject) {
        return getGuidanceMessage();
      }
      if (detectionState.hasObject) {
        return `✓ Product detected (${detectionState.confidence}%) — Tap scan`;
      }
      return detectionFeedback.message;
    }
    return getGuidanceMessage();
  };

  // ── Upload Mode ────────────────────────────────────────────────────────────
  if (uploadMode) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col bg-black">
        <canvas ref={canvasRef} className="hidden" />
        <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileUpload} />

        <div className="flex flex-col flex-1 px-5 pt-12 pb-6 overflow-y-auto">
          <div className="flex items-center gap-3 mb-5">
            <button
              onClick={() => { setUploadMode(false); setUploadSlots({ 0: null, 1: null }); setSubmitError(null); }}
              className="w-9 h-9 rounded-full flex items-center justify-center bg-white/10 border border-white/15 hover:bg-white/20 transition-colors"
            >
              <ArrowRight size={16} className="text-white rotate-180" />
            </button>
            <div>
              <p className="text-white/40 text-[9px] tracking-widest uppercase">SabiLens AI</p>
              <h2 className="text-white text-lg font-bold">Upload Images</h2>
            </div>
          </div>

          <p className="text-white/50 text-xs mb-5 leading-relaxed">
            Select the <span className="text-white font-semibold">front panel</span> and{' '}
            <span className="text-white font-semibold">back/side panel</span> of the product.
            <span className="block text-green-500 text-[10px] mt-1">NAFDAC number is usually on the back or side label.</span>
          </p>

          <div className="grid grid-cols-2 gap-3 mb-5">
            {[
              { slot: 0, label: 'Front Panel', hint: 'Brand · Logo · Name' },
              { slot: 1, label: 'Back / Side', hint: 'NAFDAC · Batch · Expiry' },
            ].map(({ slot, label, hint }) => (
              <div key={slot} className="flex flex-col gap-1.5">
                <p className="text-white/50 text-[9px] font-semibold tracking-widest uppercase">{label}</p>
                <button
                  onClick={() => openSlotPicker(slot)}
                  className={`relative h-36 rounded-xl border-2 border-dashed flex flex-col items-center justify-center overflow-hidden transition-all
                    ${uploadSlots[slot] ? 'border-green-500/60' : 'border-white/15 hover:border-green-500/40'}`}
                >
                  {uploadSlots[slot] ? (
                    <>
                      <img src={uploadSlots[slot]} alt={label} className="absolute inset-0 w-full h-full object-cover rounded-xl" />
                      <div className="absolute inset-0 bg-black/50 rounded-xl flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity">
                        <span className="text-white text-xs font-medium">Change</span>
                      </div>
                      <div className="absolute top-2 right-2 w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
                        <Check size={10} className="text-white" />
                      </div>
                    </>
                  ) : (
                    <>
                      <Image size={24} className="text-white/20 mb-1" />
                      <span className="text-white/30 text-[10px] text-center px-2">{hint}</span>
                      <span className="text-green-500 text-[10px] font-semibold mt-1">Tap to select</span>
                    </>
                  )}
                </button>
              </div>
            ))}
          </div>

          {submitError && (
            <div className="mb-4 p-2.5 rounded-xl flex items-center gap-2 bg-red-500/10 border border-red-500/30">
              <AlertCircle size={14} className="text-red-400 shrink-0" />
              <p className="text-[11px] text-red-300">{submitError}</p>
            </div>
          )}

          <button
            onClick={handleSubmitUploads}
            disabled={!uploadSlots[0] || !uploadSlots[1]}
            className={`w-full py-3.5 rounded-xl font-semibold flex items-center justify-center gap-2 transition-all text-sm
              ${uploadSlots[0] && uploadSlots[1] ? 'bg-green-500 text-white' : 'bg-white/10 text-white/30 cursor-not-allowed'}`}
          >
            <Flashlight size={16} />
            {uploadSlots[0] && uploadSlots[1] ? 'Analyse Both Images' : `Select ${!uploadSlots[0] ? 'Front' : 'Back'} Panel`}
          </button>
        </div>
      </div>
    );
  }

  // ── MAIN UI ────────────────────────────────────────────────────────────────
  return (
    <div className="fixed inset-0 flex flex-col bg-black">
      <canvas ref={canvasRef} className="hidden" />
      <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileUpload} />

      {/* ── TOP BAR ── */}
      <div className="flex-none flex items-start justify-between px-4 pt-12 pb-2">
        <button
          onClick={() => { resetScan(); navigate('/home'); }}
          className="w-8 h-8 rounded-full flex items-center justify-center bg-white/10 border border-white/15 hover:bg-white/20 transition-colors"
        >
          <X size={14} className="text-white" />
        </button>

        <div className="text-right">
          <p className="text-white/40 text-[8px] tracking-widest uppercase">SabiLens AI</p>
          <p className="text-white text-xs font-medium tracking-tight">
            {submitting ? 'Analysing…' : scanning ? `${currentPhaseData.name} Panel` : waitingForContinue ? 'Capture Complete' : 'Multimodal'}
          </p>
        </div>
      </div>

      {/* ── MODEL LOADING INDICATOR ── */}
      {isModelLoading && (
        <div className="absolute top-20 right-4 z-20 bg-black/60 backdrop-blur rounded-full px-3 py-1">
          <span className="text-white text-[10px] flex items-center gap-1">
            <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
            Loading AI model...
          </span>
        </div>
      )}

      {/* ── SCANNER BOX ── */}
      <div className="flex-1 flex flex-col items-center justify-start px-3 pt-1">
        <div className="relative w-full max-w-[360px] mx-auto">
          <div className="relative w-full rounded-2xl overflow-hidden" style={{ aspectRatio: '3/4', maxHeight: '55vh', background: '#0a0a0a' }}>
            {/* Video feed */}
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="absolute inset-0 w-full h-full object-cover"
              style={{ display: cameraActive ? 'block' : 'none' }}
            />

            {/* Camera error / loading */}
            {!cameraActive && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/80 z-10">
                {cameraPermission === 'idle' || cameraPermission === 'requesting' ? (
                  <div className="text-center">
                    <div className="w-8 h-8 border-2 border-green-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                    <p className="text-white/40 text-[10px]">Requesting camera…</p>
                  </div>
                ) : cameraPermission === 'unsupported' ? (
                  <div className="text-center px-4">
                    <AlertCircle size={28} className="mx-auto mb-2 text-yellow-400" />
                    <p className="text-white text-xs font-semibold mb-1">Camera Not Supported</p>
                    <p className="text-white/40 text-[10px]">Use Chrome, Safari, or Firefox.</p>
                  </div>
                ) : (
                  <div className="text-center px-4">
                    <CameraOff size={28} className="mx-auto mb-2 text-white/20" />
                    <p className="text-white text-xs font-semibold mb-1">Camera Access Denied</p>
                    <p className="text-white/40 text-[10px] mb-3">{cameraError}</p>
                    <button onClick={startCamera} className="px-4 py-1.5 bg-green-500 rounded-lg text-[10px] font-semibold text-white">Retry</button>
                  </div>
                )}
              </div>
            )}

            {/* Dark vignette */}
            <div className="absolute inset-0 pointer-events-none" style={{ background: 'radial-gradient(ellipse at 50% 50%, transparent 45%, rgba(0,0,0,0.45) 100%)' }} />

            {/* ── PROFESSIONAL AI SCANNING EFFECT ── */}
            {scanning && (
              <div className="absolute inset-0 pointer-events-none z-20">
                {/* Sparse grid overlay */}
                <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0, opacity: 0.12 }}>
                  <defs>
                    <pattern id="aiGrid" width="40" height="40" patternUnits="userSpaceOnUse">
                      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#22c55e" strokeWidth="0.5"/>
                    </pattern>
                  </defs>
                  <rect width="100%" height="100%" fill="url(#aiGrid)" />
                </svg>

                {/* Corner scan brackets pulsing */}
                <div style={{
                  position: 'absolute', top: '12%', left: '8%',
                  width: 28, height: 28,
                  borderTop: '2px solid rgba(34,197,94,0.9)',
                  borderLeft: '2px solid rgba(34,197,94,0.9)',
                  animation: 'scanPulse 1.5s ease-in-out infinite',
                }} />
                <div style={{
                  position: 'absolute', top: '12%', right: '8%',
                  width: 28, height: 28,
                  borderTop: '2px solid rgba(34,197,94,0.9)',
                  borderRight: '2px solid rgba(34,197,94,0.9)',
                  animation: 'scanPulse 1.5s ease-in-out infinite 0.2s',
                }} />
                <div style={{
                  position: 'absolute', bottom: '12%', left: '8%',
                  width: 28, height: 28,
                  borderBottom: '2px solid rgba(34,197,94,0.9)',
                  borderLeft: '2px solid rgba(34,197,94,0.9)',
                  animation: 'scanPulse 1.5s ease-in-out infinite 0.4s',
                }} />
                <div style={{
                  position: 'absolute', bottom: '12%', right: '8%',
                  width: 28, height: 28,
                  borderBottom: '2px solid rgba(34,197,94,0.9)',
                  borderRight: '2px solid rgba(34,197,94,0.9)',
                  animation: 'scanPulse 1.5s ease-in-out infinite 0.6s',
                }} />

                {/* 5 fixed data-point nodes — evenly distributed */}
                {[
                  { top: '22%', left: '20%' },
                  { top: '22%', left: '75%' },
                  { top: '50%', left: '48%' },
                  { top: '74%', left: '22%' },
                  { top: '74%', left: '74%' },
                ].map((pos, i) => (
                  <div
                    key={i}
                    style={{
                      position: 'absolute',
                      top: pos.top,
                      left: pos.left,
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: '#22c55e',
                      boxShadow: '0 0 8px 2px rgba(34,197,94,0.5)',
                      animation: 'scanPulse 1.8s ease-in-out infinite',
                      animationDelay: `${i * 0.3}s`,
                    }}
                  />
                ))}
              </div>
            )}

            {/* Scanning laser line */}
            {scanning && !showNextPrompt && !submitting && (
              <>
                <div
                  className="absolute left-0 right-0 h-px pointer-events-none z-30"
                  style={{
                    top: `${linePosition}%`,
                    background: 'linear-gradient(90deg, transparent, #22c55e 15%, #22c55e 85%, transparent)',
                    boxShadow: '0 0 20px 5px rgba(34,197,94,0.6)',
                    transition: 'top 25ms linear',
                  }}
                />
                <div
                  className="absolute left-0 right-0 pointer-events-none z-20"
                  style={{
                    top: `calc(${linePosition}% - 20px)`,
                    height: '40px',
                    background: 'linear-gradient(180deg, transparent, rgba(34,197,94,0.15), transparent)',
                    transition: 'top 25ms linear',
                  }}
                />
              </>
            )}

            {/* Static border */}
            <div className="absolute inset-0 pointer-events-none rounded-2xl border border-white/20" />

            {/* Corner brackets */}
            <div className="absolute inset-0 pointer-events-none" style={{ margin: '10px' }}>
              <div className="absolute top-0 left-0 w-6 h-6 border-t-2 border-l-2 border-white/60 rounded-tl-lg" />
              <div className="absolute top-0 right-0 w-6 h-6 border-t-2 border-r-2 border-white/60 rounded-tr-lg" />
              <div className="absolute bottom-0 left-0 w-6 h-6 border-b-2 border-l-2 border-white/60 rounded-bl-lg" />
              <div className="absolute bottom-0 right-0 w-6 h-6 border-b-2 border-r-2 border-white/60 rounded-br-lg" />
            </div>

            {/* Center reticle */}
            {cameraActive && !scanning && !waitingForContinue && detectionState.hasObject && (
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
                <div className="w-10 h-10 rounded-full flex items-center justify-center border border-green-500/50">
                  <div className="w-2 h-2 rounded-full bg-green-500/80" />
                </div>
              </div>
            )}

            {/* Phase indicator */}
            {scanning && !showNextPrompt && !submitting && (
              <div className="absolute top-3 left-3 bg-black/60 backdrop-blur-md rounded-full px-2 py-0.5 z-30">
                <span className="text-[9px] font-medium text-white/80">{currentPhaseData.name} Panel</span>
              </div>
            )}

            {/* Scan progress indicator */}
            {scanning && !showNextPrompt && !submitting && (
              <div className="absolute bottom-3 right-3 bg-black/60 backdrop-blur-md rounded-full px-2 py-0.5 z-30">
                <span className="text-[9px] font-medium text-green-400">{Math.round(scanProgress)}%</span>
              </div>
            )}

            {/* Success flash */}
            {showSuccess && (
              <div className="absolute inset-0 flex items-center justify-center rounded-2xl z-40 bg-black/60 backdrop-blur-sm animate-fadeIn">
                <div className="rounded-full p-4 bg-green-500 shadow-lg shadow-green-500/40 animate-bounceIn">
                  <Check size={32} className="text-white" />
                </div>
              </div>
            )}

            {/* Next phase prompt with Continue button (only for front panel) */}
            {showNextPrompt && waitingForContinue && currentPhase < TOTAL_PHASES - 1 && (
              <div className="absolute inset-0 flex flex-col items-center justify-center z-40 rounded-2xl bg-black/85 backdrop-blur-md animate-fadeIn">
                <div className="text-center px-5 w-full">
                  <div className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3 bg-green-500/15 border border-green-500">
                    <ArrowRight size={22} className="text-green-500" />
                  </div>
                  <h3 className="text-white text-sm font-bold mb-1">{currentPhaseData.captureMessage}</h3>
                  <p className="text-white/50 text-xs mb-4">{currentPhaseData.nextInstruction}</p>
                  <button
                    onClick={continueToNextPhase}
                    className="text-white px-5 py-2.5 rounded-lg font-semibold text-xs w-full max-w-[200px] mx-auto bg-green-500 hover:bg-green-600 transition-colors"
                  >
                    {currentPhaseData.continueButtonText}
                  </button>
                </div>
              </div>
            )}

            {/* Submitting overlay (auto after back panel) */}
            {submitting && (
              <div className="absolute inset-0 flex flex-col items-center justify-center z-40 rounded-2xl bg-black/85 backdrop-blur-md animate-fadeIn">
                <div className="text-center px-5">
                  <div className="w-12 h-12 border-[2px] border-green-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                  <h3 className="text-white text-sm font-bold mb-1">Analysing…</h3>
                  <p className="text-white/40 text-[10px]">Verifying your product</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── HINT PILL ── */}
        <div className="mt-3 px-3 w-full flex justify-center">
          <div className="px-4 py-2 rounded-full bg-[#1a1a1a]/90 border border-white/10 max-w-[300px]">
            <p className="text-white/90 text-xs font-medium text-center">{getHintMessage()}</p>
          </div>
        </div>
      </div>

      {/* ── BOTTOM CONTROLS ── */}
      <div className="flex-none pb-8 pt-3 px-6">
        <div className="flex items-center justify-between">
          <button onClick={() => { setUploadMode(true); setUploadSlots({ 0: null, 1: null }); setSubmitError(null); }} className="flex flex-col items-center gap-1">
            <div className="w-12 h-12 rounded-full flex items-center justify-center bg-white/10 border border-white/15 hover:bg-white/20 transition-colors">
              <Image size={18} className="text-white" />
            </div>
            <span className="text-white/50 text-[9px] font-medium">Gallery</span>
          </button>

          {scanning && !submitting && !showNextPrompt ? (
            <button onClick={resetScan} className="flex flex-col items-center gap-1">
              <div className="w-16 h-16 rounded-full flex items-center justify-center border-2 border-red-500/40">
                <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
                  <X size={20} className="text-red-400" />
                </div>
              </div>
              <span className="text-white/50 text-[9px]">Cancel</span>
            </button>
          ) : submitting ? (
            <div className="flex flex-col items-center gap-1">
              <div className="w-16 h-16 rounded-full flex items-center justify-center border-2 border-green-500/40">
                <div className="w-10 h-10 border-2 border-green-500 border-t-transparent rounded-full animate-spin" />
              </div>
              <span className="text-white/50 text-[9px]">Analysing</span>
            </div>
          ) : showNextPrompt ? null : (
            <button
              onClick={startScan}
              disabled={!canStartScan}
              className="flex flex-col items-center gap-1"
            >
              <div className={`w-16 h-16 rounded-full flex items-center justify-center transition-all ${!canStartScan ? 'opacity-40' : ''}`}>
                <div
                  className={`w-16 h-16 rounded-full ${canStartScan
                    ? 'bg-gradient-to-br from-green-400 to-green-600 shadow-lg shadow-green-500/40'
                    : 'bg-white/15'
                  }`}
                />
              </div>
              <span className={`text-[9px] font-medium ${canStartScan ? 'text-green-400' : 'text-white/40'}`}>
                {canStartScan ? 'Scan' : 'Position'}
              </span>
            </button>
          )}

          <button onClick={toggleTorch} className="flex flex-col items-center gap-1">
            <div
              className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${torchOn ? 'bg-green-500' : 'bg-white/10 border border-white/15'} hover:bg-green-600`}
            >
              <Flashlight size={18} className={torchOn ? 'text-white' : 'text-white'} />
            </div>
            <span className={`text-[9px] font-medium ${torchOn ? 'text-green-400' : 'text-white/50'}`}>Torch</span>
          </button>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes bounceIn { 0% { transform: scale(0.4); opacity: 0; } 70% { transform: scale(1.1); } 100% { transform: scale(1); opacity: 1; } }
        @keyframes scanPulse { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }
        .animate-fadeIn { animation: fadeIn 0.2s ease-out; }
        .animate-bounceIn { animation: bounceIn 0.3s ease-out; }
      `}</style>
    </div>
  );
};

export default ScanScreen;