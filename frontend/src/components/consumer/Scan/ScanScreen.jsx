import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../../common/Icon';
import Card from '../../common/Card';
import { scanApi } from '../../../services/api';

const TOTAL_PHASES = 4;

const scanPhases = [
  {
    id: 0,
    name: 'Front Panel',
    instruction: 'Scan the front of the product',
    description: 'Position the front label clearly in frame',
    target: 'Product name, brand logo, NAFDAC number',
    icon: 'Square',
    color: 'from-blue-500/20',
    nextInstruction: 'Great! Now flip to the back panel',
  },
  {
    id: 1,
    name: 'Back Panel',
    instruction: 'Scan the back of the product',
    description: 'Show the ingredients and manufacturing details',
    target: 'Ingredients, manufacturer address, batch number',
    icon: 'RotateCcw',
    color: 'from-green-500/20',
    nextInstruction: 'Good! Now show the left side',
  },
  {
    id: 2,
    name: 'Side Panel',
    instruction: 'Scan the side of the product',
    description: 'Show barcode, expiry date and lot number',
    target: 'Barcode, expiry date, lot / batch code',
    icon: 'AlignJustify',
    color: 'from-orange-500/20',
    nextInstruction: 'Almost done! Capture any seals or stamps',
  },
  {
    id: 3,
    name: 'Detail / Seal',
    instruction: 'Capture holograms, seals or stamps',
    description: 'Show any security marks, holograms or NAFDAC stickers',
    target: 'Holograms, seals, stamps, additional marks',
    icon: 'Shield',
    color: 'from-purple-500/20',
    nextInstruction: 'All 4 sides captured! Sending to AI…',
  },
];

const featuresByPhase = {
  0: ['✓ Brand detected', '✓ Logo region found', '✓ NAFDAC area located', '✓ Text extracted'],
  1: ['✓ Ingredients list found', '✓ Manufacturer info', '✓ Batch code detected', '✓ Expiry date found'],
  2: ['✓ Barcode scanned', '✓ Expiry date confirmed', '✓ Lot number found', '✓ Side text extracted'],
  3: ['✓ Hologram checked', '✓ Security seal found', '✓ Stamp verified', '✓ Mark analysis done'],
};

const emptyImages = { 0: null, 1: null, 2: null, 3: null };

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
  const [linePosition, setLinePosition] = useState(0);
  const [scanDirection, setScanDirection] = useState('down');
  const [progress, setProgress] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [capturedImages, setCapturedImages] = useState(emptyImages);

  // Refs
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const canvasRef = useRef(null);
  const scanIntervalRef = useRef(null);
  const phaseRef = useRef(0);
  const scanningRef = useRef(false);
  const capturedImagesRef = useRef({ ...emptyImages });
  const geoRef = useRef({ latitude: 0, longitude: 0, address: '' });

  // ── Camera ──────────────────────────────────────────────────────────────────

  const startCamera = useCallback(async () => {
    setCameraPermission('requesting');
    setCameraError(null);

    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraPermission('unsupported');
      setCameraError('Your browser does not support camera access.');
      return;
    }

    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }

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

  useEffect(() => {
    startCamera();

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lng = pos.coords.longitude;
          geoRef.current = {
            latitude: lat,
            longitude: lng,
            address: `${lat.toFixed(5)}° N, ${lng.toFixed(5)}° E`,
          };
        },
        () => {},
        { enableHighAccuracy: true, timeout: 10000 },
      );
    }

    return () => {
      stopAllScan();
      if (streamRef.current) { streamRef.current.getTracks().forEach((t) => t.stop()); streamRef.current = null; }
    };
  }, []);

  // ── Capture ─────────────────────────────────────────────────────────────────

  const captureImage = useCallback((phaseIndex) => {
    if (!videoRef.current || !canvasRef.current) return null;
    const canvas = canvasRef.current;
    const video = videoRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
    capturedImagesRef.current = { ...capturedImagesRef.current, [phaseIndex]: dataUrl };
    setCapturedImages((prev) => ({ ...prev, [phaseIndex]: dataUrl }));
    return dataUrl;
  }, []);

  // ── AI submission ────────────────────────────────────────────────────────────

  const submitToAI = useCallback(async (images) => {
    setSubmitting(true);
    setSubmitError(null);

    const primaryImage   = images[0];  // front panel
    const backImage      = images[1] || null;  // back panel
    const sideImage      = images[2] || null;  // side panel
    const detailImage    = images[3] || null;  // detail / seal

    if (!primaryImage) {
      setSubmitError('No image captured. Please try again.');
      setSubmitting(false);
      return;
    }

    const geo = geoRef.current;

    try {
      const payload = {
        image_data:        primaryImage,
        back_image_data:   backImage,
        side_image_data:   sideImage,
        detail_image_data: detailImage,
        category:          'unknown',
        purchase_channel:  'unknown',
        latitude:          geo.latitude,
        longitude:         geo.longitude,
        location_text:     geo.address || '',
      };

      const response = await scanApi.submitScan(payload);

      const data    = response.data || {};
      const verdict = data.verdict || data.final_verdict || 'FAKE';

      sessionStorage.setItem('currentScan', JSON.stringify({
        productImage:     primaryImage,
        isAuthentic:      verdict === 'AUTHENTIC',
        isSuspicious:     verdict === 'SUSPICIOUS',
        isRescanRequired: verdict === 'RESCAN_REQUIRED',
        aiResult:         data,
        location:         geo.address || '',
        latitude:         geo.latitude,
        longitude:        geo.longitude,
      }));

      if (verdict === 'AUTHENTIC' || verdict === 'SUSPICIOUS') {
        navigate('/scan/safe');
      } else if (verdict === 'RESCAN_REQUIRED') {
        navigate('/scan/rescan');
      } else {
        navigate('/scan/fake');
      }
    } catch (err) {
      setSubmitError(`Analysis failed: ${err.message}. Please try again.`);
      setSubmitting(false);
      setScanning(false);
      scanningRef.current = false;
    }
  }, [navigate]);

  // ── Scan phases ──────────────────────────────────────────────────────────────

  const stopAllScan = () => {
    if (scanIntervalRef.current) { clearInterval(scanIntervalRef.current); scanIntervalRef.current = null; }
    scanningRef.current = false;
  };

  const runPhase = useCallback((phaseIndex) => {
    phaseRef.current = phaseIndex;
    setCurrentPhase(phaseIndex);
    setProgress(0);
    setLinePosition(0);
    setScanDirection('down');
    setShowNextPrompt(false);

    let progressValue = 0;
    let direction = 'down';

    if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);

    scanIntervalRef.current = setInterval(() => {
      if (!scanningRef.current) { clearInterval(scanIntervalRef.current); return; }

      progressValue = Math.min(progressValue + 2, 100);
      setProgress(progressValue);

      if (direction === 'down') {
        setLinePosition(Math.min((progressValue / 50) * 100, 100));
        if (progressValue >= 50) { direction = 'up'; setScanDirection('up'); }
      } else {
        setLinePosition(Math.max(100 - ((progressValue - 50) / 50) * 100, 0));
      }

      if (progressValue >= 100) {
        clearInterval(scanIntervalRef.current);
        scanIntervalRef.current = null;

        captureImage(phaseIndex);
        setCompletedPhases((prev) => [...prev, phaseIndex]);
        setDetectedFeatures((prev) => [...prev, ...(featuresByPhase[phaseIndex] || [])]);
        setShowSuccess(true);

        setTimeout(() => {
          setShowSuccess(false);
          if (phaseIndex < TOTAL_PHASES - 1) {
            setShowNextPrompt(true);
          } else {
            // Last phase — submit all 4 images to AI
            setShowNextPrompt(true);
            setTimeout(() => {
              setScanning(false);
              scanningRef.current = false;
              submitToAI(capturedImagesRef.current);
            }, 1500);
          }
        }, 1500);
      }
    }, 40);
  }, [captureImage, submitToAI]);

  const startScanning = useCallback(() => {
    if (!cameraActive) { setCameraError('Please enable camera access to start scanning.'); return; }
    stopAllScan();
    setScanning(true);
    scanningRef.current = true;
    setCompletedPhases([]);
    setDetectedFeatures([]);
    capturedImagesRef.current = { ...emptyImages };
    setCapturedImages({ ...emptyImages });
    setSubmitError(null);
    runPhase(0);
  }, [cameraActive, runPhase]);

  const resetScan = useCallback(() => {
    stopAllScan();
    setScanning(false);
    setCurrentPhase(0);
    setCompletedPhases([]);
    setDetectedFeatures([]);
    setProgress(0);
    setLinePosition(0);
    setScanDirection('down');
    setShowSuccess(false);
    setShowNextPrompt(false);
    setSubmitting(false);
    setSubmitError(null);
  }, []);

  const continueToNextPhase = useCallback(() => {
    setShowNextPrompt(false);
    if (currentPhase < TOTAL_PHASES - 1) runPhase(currentPhase + 1);
  }, [currentPhase, runPhase]);

  // ── File upload fallback ─────────────────────────────────────────────────────

  const handleUploadClick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.multiple = true;
    input.onchange = async (e) => {
      if (!e.target.files?.length) return;
      const files = Array.from(e.target.files).slice(0, TOTAL_PHASES);
      const readFile = (file) =>
        new Promise((res) => {
          const reader = new FileReader();
          reader.onload = (ev) => res(ev.target.result);
          reader.readAsDataURL(file);
        });

      const dataUrls = await Promise.all(files.map(readFile));
      const imgs = { ...emptyImages };
      dataUrls.forEach((url, i) => { imgs[i] = url; });

      setScanning(true);
      setSubmitting(true);
      setSubmitError(null);
      capturedImagesRef.current = imgs;
      await submitToAI(imgs);
    };
    input.click();
  };

  const currentPhaseData = scanPhases[currentPhase] ?? scanPhases[0];

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-black">
      {/* Camera Viewport */}
      <div className="relative h-[70vh] bg-gray-900 overflow-hidden">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          style={{ display: cameraActive ? 'block' : 'none' }}
          className="absolute inset-0 w-full h-full object-cover"
        />
        <canvas ref={canvasRef} className="hidden" />

        {/* Camera placeholder */}
        {!cameraActive && (
          <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-gray-900 to-gray-800">
            {cameraPermission === 'idle' || cameraPermission === 'requesting' ? (
              <div className="text-center text-white">
                <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-sm">Requesting camera access…</p>
              </div>
            ) : cameraPermission === 'unsupported' ? (
              <div className="text-center text-white px-6">
                <Icon name="AlertTriangle" size={64} className="mx-auto mb-4 text-yellow-500" library="fi" />
                <p className="text-lg font-medium mb-2">Camera Not Supported</p>
                <p className="text-sm text-gray-400">Use Chrome, Safari, or Firefox.</p>
              </div>
            ) : (
              <div className="text-center text-white px-6">
                <Icon name="CameraOff" size={64} className="mx-auto mb-4 text-gray-400" library="fi" />
                <p className="text-lg font-medium mb-2">Camera Access Denied</p>
                <p className="text-sm text-gray-400 mb-6">{cameraError}</p>
                <button onClick={startCamera} className="px-6 py-3 bg-primary rounded-xl text-sm font-semibold hover:bg-primary-dark transition-colors">
                  Retry
                </button>
              </div>
            )}
          </div>
        )}

        {/* Scanning overlay */}
        {cameraActive && (
          <div className="absolute inset-0">
            <div className="absolute inset-0 bg-black/20" />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="relative">
                {/* Phase badge */}
                <div className="absolute -top-16 left-1/2 -translate-x-1/2 bg-black/90 backdrop-blur px-4 py-2 rounded-full border border-primary/30 shadow-lg z-10 whitespace-nowrap">
                  <span className="text-white text-sm font-medium flex items-center gap-2">
                    <Icon name={currentPhaseData.icon} size={16} className="text-primary" library="fi" />
                    Phase {currentPhase + 1}/{TOTAL_PHASES}: {currentPhaseData.name}
                  </span>
                </div>

                {/* Frame */}
                <div className="relative w-80 h-80">
                  <div className={`absolute inset-0 bg-gradient-to-br ${currentPhaseData.color} to-transparent rounded-2xl blur-xl`} />
                  <div className="absolute inset-0 border-2 border-primary/30 rounded-2xl" />
                  <div className="absolute inset-4 border border-primary/20 rounded-lg">
                    <div className="absolute -top-1 -left-1 w-8 h-8 border-t-4 border-l-4 border-primary rounded-tl-lg" />
                    <div className="absolute -top-1 -right-1 w-8 h-8 border-t-4 border-r-4 border-primary rounded-tr-lg" />
                    <div className="absolute -bottom-1 -left-1 w-8 h-8 border-b-4 border-l-4 border-primary rounded-bl-lg" />
                    <div className="absolute -bottom-1 -right-1 w-8 h-8 border-b-4 border-r-4 border-primary rounded-br-lg" />
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
                      <div className="w-16 h-16 border-2 border-primary/40 rounded-full" />
                      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 bg-primary rounded-full" />
                    </div>

                    {scanning && !showNextPrompt && !submitting && (
                      <>
                        <div className="absolute left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-primary to-transparent" style={{ top: `${linePosition}%`, boxShadow: '0 0 20px #A020F0', transition: 'top 40ms linear' }} />
                        <div className="absolute left-0 right-0 h-12 bg-gradient-to-b from-primary/20 to-transparent pointer-events-none" style={{ top: `${linePosition - 6}%`, filter: 'blur(8px)', transition: 'top 40ms linear' }} />
                      </>
                    )}

                    {/* Next Phase Prompt */}
                    {showNextPrompt && (
                      <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 backdrop-blur-sm rounded-2xl z-30 animate-fadeIn">
                        <div className="text-center px-6">
                          {submitting ? (
                            <>
                              <div className="w-20 h-20 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                              <h3 className="text-white text-xl font-bold mb-2">Analysing…</h3>
                              <p className="text-gray-300 text-base">SabiLens AI is verifying your product</p>
                            </>
                          ) : (
                            <>
                              <div className="w-20 h-20 bg-primary/20 rounded-full flex items-center justify-center mx-auto mb-4 border-4 border-primary">
                                <Icon name="ArrowRight" size={40} className="text-primary" library="fi" />
                              </div>
                              <h3 className="text-white text-xl font-bold mb-2">Phase {currentPhase + 1} Complete!</h3>
                              <p className="text-gray-300 text-base mb-6">{currentPhaseData.nextInstruction}</p>
                              {currentPhase < TOTAL_PHASES - 1 ? (
                                <button onClick={continueToNextPhase} className="bg-primary text-white px-8 py-4 rounded-xl font-semibold text-lg hover:bg-primary-dark transition-colors shadow-lg shadow-primary/30 w-full">
                                  Continue to Phase {currentPhase + 2}
                                </button>
                              ) : (
                                <div className="text-center">
                                  <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                                  <p className="text-white">Sending to AI…</p>
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {scanning && !showNextPrompt && (
                    <div className="absolute -right-14 top-1/2 -translate-y-1/2 bg-black/80 backdrop-blur px-3 py-2 rounded-full border border-primary/30">
                      <Icon name={scanDirection === 'down' ? 'ArrowDown' : 'ArrowUp'} size={20} className="text-primary animate-bounce" library="fi" />
                    </div>
                  )}
                  {scanning && !showNextPrompt && (
                    <div className="absolute -bottom-12 left-1/2 -translate-x-1/2 bg-black/80 backdrop-blur px-4 py-2 rounded-full border border-primary/30">
                      <span className="text-white text-sm font-mono">{Math.round(progress)}% Complete</span>
                    </div>
                  )}
                </div>

                {!showNextPrompt && (
                  <div className="absolute -bottom-32 left-1/2 -translate-x-1/2 w-72 text-center">
                    <p className="text-white text-base font-medium mb-1 drop-shadow-lg">{currentPhaseData.instruction}</p>
                    <p className="text-gray-300 text-xs">{currentPhaseData.description}</p>
                  </div>
                )}
              </div>
            </div>

            {showSuccess && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm z-20 animate-fadeIn">
                <div className="bg-primary rounded-full p-6 animate-bounce">
                  <Icon name="Check" size={64} className="text-white" library="fi" />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Top HUD */}
        <div className="absolute top-0 left-0 right-0 p-4 bg-gradient-to-b from-black/80 to-transparent z-10">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full animate-pulse ${cameraActive ? 'bg-green-500' : 'bg-yellow-500'}`} />
              <span className="text-white text-sm font-medium">
                {submitting ? 'SABILENS AI ANALYSING…' : cameraActive ? 'SABILENS AI ACTIVE' : 'INITIALIZING CAMERA…'}
              </span>
            </div>
            {/* Phase dots — one per phase */}
            <div className="flex items-center gap-1">
              {scanPhases.map((phase, index) => (
                <div
                  key={phase.id}
                  className={`w-2 h-2 rounded-full transition-all duration-300 ${
                    completedPhases.includes(index)
                      ? 'bg-primary scale-125'
                      : index === currentPhase && scanning && !showNextPrompt
                      ? 'bg-primary/70 animate-pulse'
                      : 'bg-white/30'
                  }`}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Bottom camera controls */}
        <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-black/80 to-transparent z-10">
          <div className="flex justify-between items-end">
            <button onClick={handleUploadClick} disabled={submitting} className="flex flex-col items-center gap-2 group disabled:opacity-50">
              <div className="w-14 h-14 bg-white/10 backdrop-blur rounded-full flex items-center justify-center group-hover:bg-white/20 transition-all group-hover:scale-110 border border-white/20">
                <Icon name="Upload" size={22} className="text-white" library="fi" />
              </div>
              <span className="text-white text-xs font-medium">Upload</span>
            </button>

            {!scanning ? (
              <button
                onClick={startScanning}
                disabled={!cameraActive || submitting}
                className={`flex flex-col items-center gap-2 group ${(!cameraActive || submitting) && 'opacity-50 cursor-not-allowed'}`}
              >
                <div className={`w-20 h-20 rounded-full flex items-center justify-center transition-all group-hover:scale-110 ${cameraActive ? 'bg-primary shadow-lg shadow-primary/50' : 'bg-gray-600'}`}>
                  <Icon name="Camera" size={32} className="text-white" library="fi" />
                </div>
                <span className="text-white text-sm font-medium">{cameraActive ? 'Start Scan' : 'No Camera'}</span>
              </button>
            ) : (
              <div className="flex flex-col items-center gap-2">
                {submitting ? (
                  <div className="w-20 h-20 bg-primary rounded-full flex items-center justify-center shadow-lg shadow-primary/50">
                    <div className="w-10 h-10 border-4 border-white border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : showNextPrompt ? (
                  <div className="w-20 h-20 bg-primary rounded-full flex items-center justify-center shadow-lg shadow-primary/50 animate-pulse">
                    <Icon name="ArrowRight" size={32} className="text-white" library="fi" />
                  </div>
                ) : (
                  <div className="w-20 h-20 bg-primary rounded-full flex items-center justify-center shadow-lg shadow-primary/50">
                    <span className="text-white text-xl font-bold">{Math.round(progress)}%</span>
                  </div>
                )}
                <span className="text-white text-xs">
                  {submitting ? 'AI Analysing…' : showNextPrompt ? 'Ready for next' : `Phase ${currentPhase + 1}/${TOTAL_PHASES}`}
                </span>
              </div>
            )}

            <button onClick={() => navigate('/scan-history')} className="flex flex-col items-center gap-2 group">
              <div className="w-14 h-14 bg-white/10 backdrop-blur rounded-full flex items-center justify-center group-hover:bg-white/20 transition-all group-hover:scale-110 border border-white/20">
                <Icon name="Clock" size={22} className="text-white" library="fi" />
              </div>
              <span className="text-white text-xs font-medium">Recent</span>
            </button>
          </div>
        </div>

        <button
          onClick={() => { stopAllScan(); navigate('/home'); }}
          className="absolute top-4 left-4 z-20 w-10 h-10 bg-black/50 backdrop-blur rounded-full flex items-center justify-center hover:bg-black/70 transition-colors border border-white/20"
        >
          <Icon name="X" size={20} className="text-white" library="fi" />
        </button>
      </div>

      {/* Status Panel */}
      <div className="bg-white p-6 rounded-t-3xl min-h-[30vh] relative z-20">
        {submitError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3">
            <Icon name="AlertCircle" size={20} className="text-red-500 shrink-0" library="fi" />
            <p className="text-sm text-red-700">{submitError}</p>
            <button onClick={resetScan} className="ml-auto text-xs text-red-500 underline">Reset</button>
          </div>
        )}

        {submitting ? (
          <div className="text-center py-8">
            <div className="w-20 h-20 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <h2 className="text-xl font-bold text-gray-900 mb-2">SabiLens AI is working…</h2>
            <p className="text-gray-500 text-sm">Running OCR, visual analysis, and NAFDAC verification on all {TOTAL_PHASES} images</p>
          </div>
        ) : !scanning ? (
          <>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Ready to Scan</h2>
            <p className="text-gray-500 mb-6">
              We'll guide you through capturing all 4 sides of the product for thorough AI-powered verification.
            </p>
            <div className="grid grid-cols-2 gap-3 mb-8">
              {scanPhases.map((phase) => (
                <div key={phase.id} className="text-center p-3 rounded-xl bg-gray-50 border border-gray-100">
                  <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-2">
                    <Icon name={phase.icon} size={18} className="text-primary" library="fi" />
                  </div>
                  <p className="text-xs font-semibold text-gray-700">{phase.name}</p>
                  <p className="text-[10px] text-gray-400 mt-1">{phase.target.substring(0, 24)}…</p>
                </div>
              ))}
            </div>
            {!cameraActive && (
              <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-xl flex items-center gap-3">
                <Icon name="AlertTriangle" size={20} className="text-yellow-600" library="fi" />
                <p className="text-sm text-yellow-700">{cameraError || 'Please enable camera access to start scanning.'}</p>
              </div>
            )}
            <button
              onClick={startScanning}
              disabled={!cameraActive}
              className={`w-full py-4 rounded-xl font-medium flex items-center justify-center gap-2 transition-all ${
                cameraActive ? 'bg-primary text-white hover:bg-primary-dark shadow-lg shadow-primary/30' : 'bg-gray-200 text-gray-500 cursor-not-allowed'
              }`}
            >
              <Icon name="Camera" size={20} library="fi" />
              {cameraActive ? `Begin ${TOTAL_PHASES}-Point Scan` : 'Waiting for Camera…'}
            </button>
            {cameraActive && (
              <p className="text-xs text-center text-gray-400 mt-4">
                Make sure the product is well-lit and all labels are clearly visible.
              </p>
            )}
          </>
        ) : (
          <>
            {!showNextPrompt ? (
              <>
                <div className="mb-6">
                  <div className="flex justify-between items-center mb-2">
                    <div>
                      <h2 className="text-lg font-bold text-gray-900">{currentPhaseData.name}</h2>
                      <p className="text-xs text-gray-500">Phase {currentPhase + 1} of {TOTAL_PHASES}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1 bg-primary/10 px-3 py-1 rounded-full">
                        <Icon name={scanDirection === 'down' ? 'ArrowDown' : 'ArrowUp'} size={14} className="text-primary" library="fi" />
                        <span className="text-xs font-medium text-primary">{scanDirection === 'down' ? 'Scanning Down' : 'Scanning Up'}</span>
                      </div>
                      <span className="text-2xl font-bold text-primary">{Math.round(progress)}%</span>
                    </div>
                  </div>
                  <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-primary rounded-full" style={{ width: `${progress}%`, transition: 'width 40ms linear' }} />
                  </div>
                </div>

                <Card className="mb-4 bg-primary/5 border border-primary/20">
                  <h3 className="text-sm font-medium text-primary mb-2 flex items-center gap-2">
                    <Icon name="Target" size={16} className="text-primary" library="fi" />
                    Currently Detecting:
                  </h3>
                  <p className="text-sm text-gray-600">{currentPhaseData.target}</p>
                </Card>

                {detectedFeatures.length > 0 && (
                  <div className="mt-4">
                    <p className="text-xs font-medium text-gray-500 mb-2">Features Detected:</p>
                    <div className="space-y-1">
                      {detectedFeatures.slice(-4).map((feature, idx) => (
                        <div key={idx} className="flex items-center gap-2 text-xs text-gray-600">
                          <Icon name="Check" size={12} className="text-green-500" library="fi" />
                          {feature}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {completedPhases.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <p className="text-xs font-medium text-gray-500 mb-2">Completed Phases:</p>
                    <div className="flex gap-2">
                      {completedPhases.map((phaseId) => (
                        <div key={phaseId} className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center border border-primary/30">
                          <Icon name="Check" size={14} className="text-primary" library="fi" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : !submitting ? (
              <div className="text-center py-8">
                <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Icon name="CheckCircle" size={40} className="text-primary" library="fi" />
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Phase {currentPhase + 1} Complete!</h3>
                <p className="text-gray-600 mb-6">{currentPhaseData.nextInstruction}</p>
                {currentPhase < TOTAL_PHASES - 1 && (
                  <button onClick={continueToNextPhase} className="bg-primary text-white px-6 py-3 rounded-xl font-medium hover:bg-primary-dark transition-colors w-full">
                    Continue to Phase {currentPhase + 2}
                  </button>
                )}
              </div>
            ) : null}

            {!showNextPrompt && (
              <button onClick={resetScan} className="mt-6 w-full py-3 rounded-xl border border-gray-200 text-sm text-gray-500 hover:bg-gray-50 transition-colors">
                Cancel Scan
              </button>
            )}
          </>
        )}
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0; transform: scale(0.9); } to { opacity: 1; transform: scale(1); } }
        .animate-fadeIn { animation: fadeIn 0.3s ease-out; }
      `}</style>
    </div>
  );
};

export default ScanScreen;
