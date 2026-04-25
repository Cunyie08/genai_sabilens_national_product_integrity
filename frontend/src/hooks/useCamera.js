import { useState, useRef, useCallback } from 'react';

const useCamera = () => {
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const [cameraPermission, setCameraPermission] = useState('idle');
  const videoRef = useRef(null);
  const streamRef = useRef(null);

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
        video: { 
          facingMode: { ideal: 'environment' }, 
          width: { ideal: 1280 }, 
          height: { ideal: 720 } 
        },
        audio: false,
      });

      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }

      video.srcObject = stream;
      await new Promise((resolve, reject) => {
        video.onloadedmetadata = resolve;
        video.onerror = reject;
      });
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

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  }, []);

  return {
    videoRef,
    cameraActive,
    cameraError,
    cameraPermission,
    startCamera,
    stopCamera,
  };
};

export default useCamera;