// src/hooks/useMediaPipeDetection.js
import { useState, useEffect, useRef, useCallback } from 'react';

const useMediaPipeDetection = (videoRef, isActive = true, onReady = null) => {
  const [detectionState, setDetectionState] = useState({
    hasObject: false,
    isInsideBox: false,
    isLargeEnough: false,
    isCentered: false,
    isStable: false,
    isReady: false,
    confidence: 0,
    position: null,
  });
  
  const [isModelLoading, setIsModelLoading] = useState(false); // No model loading needed
  const [modelError, setModelError] = useState(null);
  
  const animationRef = useRef(null);
  const prevBoxRef = useRef(null);
  const stableFramesRef = useRef(0);
  const lastDetectionRef = useRef(Date.now());
  const hasTriggeredRef = useRef(false);
  const onReadyCallbackRef = useRef(onReady);

  useEffect(() => {
    onReadyCallbackRef.current = onReady;
  }, [onReady]);

  // Scanner box - 70% of frame, centered
  const getScanBox = useCallback((width, height) => ({
    x: width * 0.15,
    y: height * 0.15,
    width: width * 0.7,
    height: height * 0.7
  }), []);

  // Detect product sachets by looking for text and rectangular shapes
  const detectProduct = useCallback((video) => {
    if (!video || video.videoWidth === 0) return null;

    // Create a small canvas for analysis (fast)
    const canvas = document.createElement('canvas');
    const scale = 0.3; // Scale down for performance
    canvas.width = video.videoWidth * scale;
    canvas.height = video.videoHeight * scale;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imageData.data;

    // Look for high contrast areas (text on product)
    let highContrastPixels = 0;
    let totalPixels = 0;
    
    // Also track edges for rectangular shape detection
    let horizontalEdges = 0;
    let verticalEdges = 0;
    
    // Scan the image in a grid for performance
    for (let y = 4; y < canvas.height - 4; y += 6) {
      for (let x = 4; x < canvas.width - 4; x += 6) {
        const idx = (y * canvas.width + x) * 4;
        const brightness = (data[idx] + data[idx + 1] + data[idx + 2]) / 3;
        
        // Check horizontal contrast (left/right)
        const leftIdx = (y * canvas.width + (x - 2)) * 4;
        const rightIdx = (y * canvas.width + (x + 2)) * 4;
        const leftBright = (data[leftIdx] + data[leftIdx + 1] + data[leftIdx + 2]) / 3;
        const rightBright = (data[rightIdx] + data[rightIdx + 1] + data[rightIdx + 2]) / 3;
        const horizContrast = Math.abs(leftBright - rightBright);
        
        // Check vertical contrast (up/down)
        const upIdx = ((y - 2) * canvas.width + x) * 4;
        const downIdx = ((y + 2) * canvas.width + x) * 4;
        const upBright = (data[upIdx] + data[upIdx + 1] + data[upIdx + 2]) / 3;
        const downBright = (data[downIdx] + data[downIdx + 1] + data[downIdx + 2]) / 3;
        const vertContrast = Math.abs(upBright - downBright);
        
        if (horizContrast > 25) horizontalEdges++;
        if (vertContrast > 25) verticalEdges++;
        if (horizContrast > 20 || vertContrast > 20) highContrastPixels++;
        
        totalPixels++;
      }
    }
    
    const contrastRatio = highContrastPixels / totalPixels;
    const hasText = contrastRatio > 0.06;
    const hasRectangularShape = horizontalEdges > totalPixels * 0.1 && verticalEdges > totalPixels * 0.1;
    
    // A product sachet typically has text AND is somewhat rectangular
    if (hasText || hasRectangularShape) {
      // Create a bounding box covering the center area (most likely product location)
      const centerX = video.videoWidth * 0.5;
      const centerY = video.videoHeight * 0.5;
      const width = video.videoWidth * 0.6;
      const height = video.videoHeight * 0.6;
      
      // Calculate confidence based on text presence and shape
      let confidence = 55;
      if (hasText) confidence += 25;
      if (hasRectangularShape) confidence += 20;
      confidence = Math.min(95, confidence);
      
      console.log(`🔍 Product detection: text=${hasText}, shape=${hasRectangularShape}, confidence=${confidence}%`);
      
      return {
        bbox: {
          originX: centerX - width / 2,
          originY: centerY - height / 2,
          width: width,
          height: height
        },
        confidence: confidence
      };
    }
    
    return null;
  }, []);

  // Main detection logic
  const detect = useCallback(() => {
    const video = videoRef?.current;
    if (!video || video.videoWidth === 0 || video.videoHeight === 0) return;

    try {
      const videoWidth = video.videoWidth;
      const videoHeight = video.videoHeight;
      const scanBox = getScanBox(videoWidth, videoHeight);
      
      // Detect product using our custom method
      const detection = detectProduct(video);
      
      const hasObject = detection !== null;
      let isInside = false;
      let isLargeEnough = false;
      let isCentered = false;
      let isStable = false;
      let confidence = 0;
      let position = null;
      
      if (hasObject) {
        const bbox = detection.bbox;
        confidence = detection.confidence;
        
        position = {
          originX: bbox.originX,
          originY: bbox.originY,
          width: bbox.width,
          height: bbox.height
        };
        
        // Check if inside scan box
        isInside = (
          bbox.originX + bbox.width > scanBox.x &&
          bbox.originX < scanBox.x + scanBox.width &&
          bbox.originY + bbox.height > scanBox.y &&
          bbox.originY < scanBox.y + scanBox.height
        );
        
        // Check if large enough (minimum 3% of frame)
        const frameArea = videoWidth * videoHeight;
        const objectArea = bbox.width * bbox.height;
        isLargeEnough = objectArea > frameArea * 0.03;
        
        // Check if centered
        const centerX = bbox.originX + bbox.width / 2;
        const centerY = bbox.originY + bbox.height / 2;
        const boxCenterX = scanBox.x + scanBox.width / 2;
        const boxCenterY = scanBox.y + scanBox.height / 2;
        const distance = Math.hypot(centerX - boxCenterX, centerY - boxCenterY);
        isCentered = distance < scanBox.width * 0.4;
        
        // Stability check
        if (prevBoxRef.current) {
          const dx = Math.abs(bbox.originX - prevBoxRef.current.originX);
          const dy = Math.abs(bbox.originY - prevBoxRef.current.originY);
          isStable = (dx + dy) < 40;
        } else {
          isStable = true;
        }
        
        // Update stable frames
        if (isInside && isLargeEnough) {
          stableFramesRef.current = Math.min(10, stableFramesRef.current + 1);
        } else {
          stableFramesRef.current = Math.max(0, stableFramesRef.current - 1);
        }
        
        prevBoxRef.current = bbox;
      } else {
        stableFramesRef.current = Math.max(0, stableFramesRef.current - 1);
        prevBoxRef.current = null;
      }
      
      // Ready when stable for 5 frames AND confidence is good
      const isReady = hasObject && isInside && isLargeEnough && isCentered && stableFramesRef.current >= 5;
      
      if (isReady && !hasTriggeredRef.current && onReadyCallbackRef.current) {
        console.log('✅ PRODUCT READY TO SCAN!');
        hasTriggeredRef.current = true;
        onReadyCallbackRef.current();
      }
      
      if (!isReady) hasTriggeredRef.current = false;
      
      setDetectionState({
        hasObject,
        isInsideBox: isInside,
        isLargeEnough,
        isCentered,
        isStable,
        isReady,
        confidence,
        position
      });
      
    } catch (error) {
      console.error('Detection error:', error);
    }
  }, [videoRef, getScanBox, detectProduct]);

  // Detection loop - runs every 200ms
  const detectFrame = useCallback(() => {
    const video = videoRef?.current;
    if (!video || video.paused || video.ended || video.videoWidth === 0) {
      animationRef.current = requestAnimationFrame(detectFrame);
      return;
    }
    
    const now = Date.now();
    if (now - lastDetectionRef.current >= 200) {
      lastDetectionRef.current = now;
      detect();
    }
    
    animationRef.current = requestAnimationFrame(detectFrame);
  }, [videoRef, detect]);

  useEffect(() => {
    if (!isActive) {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      return;
    }
    
    lastDetectionRef.current = Date.now();
    animationRef.current = requestAnimationFrame(detectFrame);
    
    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [isActive, detectFrame]);

  const getDetailedFeedback = useCallback(() => {
    if (!detectionState.hasObject) {
      return { message: '📦 Place product in frame', progress: 0, color: 'text-yellow-400' };
    }
    if (!detectionState.isLargeEnough) {
      return { message: '🔍 Move product closer', progress: 25, color: 'text-yellow-400' };
    }
    if (!detectionState.isInsideBox) {
      return { message: '🎯 Center product in frame', progress: 50, color: 'text-yellow-400' };
    }
    if (!detectionState.isCentered) {
      return { message: '⬅️ Center the product', progress: 75, color: 'text-yellow-400' };
    }
    if (!detectionState.isStable) {
      return { message: '✋ Hold steady', progress: 90, color: 'text-blue-400' };
    }
    if (detectionState.isReady) {
      return { message: `✅ Ready to scan`, progress: 100, color: 'text-green-400' };
    }
    return { message: 'Position product in frame', progress: 0, color: 'text-white/60' };
  }, [detectionState]);

  return {
    isProductDetected: detectionState.isReady,
    detectionConfidence: detectionState.confidence,
    detectionPosition: detectionState.position,
    detectionState,
    getDetailedFeedback,
    isModelLoading,
    modelError,
    resetTrigger: () => { hasTriggeredRef.current = false; }
  };
};

export default useMediaPipeDetection;