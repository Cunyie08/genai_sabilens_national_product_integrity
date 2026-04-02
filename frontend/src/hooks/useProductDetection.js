import { useState, useRef, useEffect, useCallback } from 'react';

const useProductDetection = (videoRef, isActive = true) => {
  const [isProductDetected, setIsProductDetected] = useState(false);
  const [detectionConfidence, setDetectionConfidence] = useState(0);
  const [isAnalyzing, setIsAnalyzing] = useState(true);
  const [detectionDetails, setDetectionDetails] = useState(null);
  const animationRef = useRef(null);
  const lastDetectionRef = useRef(Date.now());
  const canvasRef = useRef(null);
  const frameBufferRef = useRef([]); // For temporal consistency

  // Create canvas for analysis
  useEffect(() => {
    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas');
    }
    setIsAnalyzing(true);
    const timer = setTimeout(() => setIsAnalyzing(false), 1000);
    return () => clearTimeout(timer);
  }, []);

  // Detect if image has text-like regions (product labels)
  const detectTextRegions = (ctx, width, height) => {
    const imageData = ctx.getImageData(0, 0, width, height);
    const data = imageData.data;
    
    let highContrastCount = 0;
    let mediumContrastCount = 0;
    let totalSamples = 0;
    
    // Sample grid for text detection
    for (let y = 4; y < height - 4; y += 8) {
      for (let x = 4; x < width - 4; x += 8) {
        const idx = (y * width + x) * 4;
        const r = data[idx];
        const g = data[idx + 1];
        const b = data[idx + 2];
        const brightness = (r + g + b) / 3;
        
        // Check surrounding pixels for contrast
        let localContrast = 0;
        let neighborCount = 0;
        
        for (let dy = -2; dy <= 2; dy++) {
          for (let dx = -2; dx <= 2; dx++) {
            const nIdx = ((y + dy) * width + (x + dx)) * 4;
            if (nIdx >= 0 && nIdx < data.length) {
              const nBrightness = (data[nIdx] + data[nIdx+1] + data[nIdx+2]) / 3;
              localContrast += Math.abs(brightness - nBrightness);
              neighborCount++;
            }
          }
        }
        
        const avgContrast = localContrast / neighborCount;
        
        if (avgContrast > 35) {
          highContrastCount++;
        } else if (avgContrast > 18) {
          mediumContrastCount++;
        }
        totalSamples++;
      }
    }
    
    const highContrastRatio = highContrastCount / totalSamples;
    const mediumContrastRatio = mediumContrastCount / totalSamples;
    
    // Text regions have high local contrast (character edges)
    return {
      hasText: highContrastRatio > 0.05 && mediumContrastRatio > 0.12,
      textConfidence: Math.min(100, Math.round((highContrastRatio * 200) + (mediumContrastRatio * 100)))
    };
  };

  // Detect edges and shapes (packaging boundaries)
  const detectEdgesAndShapes = (ctx, width, height) => {
    const imageData = ctx.getImageData(0, 0, width, height);
    const data = imageData.data;
    
    // Create simple edge map
    const edges = [];
    let horizontalEdges = 0;
    let verticalEdges = 0;
    let totalEdges = 0;
    
    for (let y = 2; y < height - 2; y += 4) {
      for (let x = 2; x < width - 2; x += 4) {
        const idx = (y * width + x) * 4;
        const brightness = (data[idx] + data[idx+1] + data[idx+2]) / 3;
        
        // Horizontal gradient
        const leftIdx = (y * width + (x - 1)) * 4;
        const rightIdx = (y * width + (x + 1)) * 4;
        const leftBrightness = (data[leftIdx] + data[leftIdx+1] + data[leftIdx+2]) / 3;
        const rightBrightness = (data[rightIdx] + data[rightIdx+1] + data[rightIdx+2]) / 3;
        const horizGrad = Math.abs(leftBrightness - rightBrightness);
        
        // Vertical gradient
        const upIdx = ((y - 1) * width + x) * 4;
        const downIdx = ((y + 1) * width + x) * 4;
        const upBrightness = (data[upIdx] + data[upIdx+1] + data[upIdx+2]) / 3;
        const downBrightness = (data[downIdx] + data[downIdx+1] + data[downIdx+2]) / 3;
        const vertGrad = Math.abs(upBrightness - downBrightness);
        
        if (horizGrad > 25) horizontalEdges++;
        if (vertGrad > 25) verticalEdges++;
        if (horizGrad > 20 || vertGrad > 20) totalEdges++;
      }
    }
    
    const totalSamples = ((width - 4) / 4) * ((height - 4) / 4);
    const edgeDensity = totalEdges / totalSamples;
    const horizVertRatio = horizontalEdges / (verticalEdges + 1);
    
    // Product packaging typically has:
    // - Moderate edge density (not too cluttered, not empty)
    // - Balanced horizontal and vertical edges (rectangular shape)
    const hasStructure = edgeDensity > 0.12 && edgeDensity < 0.45;
    const isRectangular = horizVertRatio > 0.6 && horizVertRatio < 1.6;
    
    return {
      hasEdges: hasStructure,
      hasRectangularShape: isRectangular,
      edgeConfidence: Math.min(100, Math.round(edgeDensity * 180))
    };
  };

  // Detect color consistency and saturation (product packaging often has vibrant colors)
  const detectColorProfile = (ctx, width, height) => {
    const imageData = ctx.getImageData(0, 0, width, height);
    const data = imageData.data;
    
    let saturationSum = 0;
    let brightnessVariance = 0;
    let brightnessValues = [];
    let totalPixels = 0;
    
    for (let y = 0; y < height; y += 6) {
      for (let x = 0; x < width; x += 6) {
        const idx = (y * width + x) * 4;
        const r = data[idx];
        const g = data[idx + 1];
        const b = data[idx + 2];
        
        const max = Math.max(r, g, b);
        const min = Math.min(r, g, b);
        const saturation = max === 0 ? 0 : (max - min) / max * 100;
        saturationSum += saturation;
        
        const brightness = (r + g + b) / 3;
        brightnessValues.push(brightness);
        totalPixels++;
      }
    }
    
    const avgSaturation = saturationSum / totalPixels;
    
    // Calculate brightness variance
    const avgBrightness = brightnessValues.reduce((a, b) => a + b, 0) / totalPixels;
    const variance = brightnessValues.reduce((sum, val) => sum + Math.pow(val - avgBrightness, 2), 0) / totalPixels;
    
    // Product packaging has:
    // - Moderate to high saturation (vibrant colors)
    // - Balanced brightness distribution (not pure white/black)
    const hasVibrantColors = avgSaturation > 25;
    const hasBalancedLighting = variance > 400 && variance < 3000;
    
    return {
      hasVibrantColors,
      hasBalancedLighting,
      colorConfidence: Math.min(100, Math.round(avgSaturation * 1.2))
    };
  };

  // Detect if frame contains a product package (main detection function)
  const detectProductPackaging = useCallback((video) => {
    if (!video || video.videoWidth === 0 || video.videoHeight === 0 || !canvasRef.current) {
      return { isProduct: false, confidence: 0, details: null };
    }
    
    const canvas = canvasRef.current;
    // Use medium resolution for good detection without performance hit
    canvas.width = 320;
    canvas.height = 240;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Run all detection methods
    const textDetection = detectTextRegions(ctx, canvas.width, canvas.height);
    const edgeDetection = detectEdgesAndShapes(ctx, canvas.width, canvas.height);
    const colorDetection = detectColorProfile(ctx, canvas.width, canvas.height);
    
    // Combine scores with weights
    let totalScore = 0;
    let maxScore = 0;
    
    // Text detection (most important for product labels)
    if (textDetection.hasText) {
      totalScore += textDetection.textConfidence * 0.4;
      maxScore += 100 * 0.4;
    }
    
    // Edge and shape detection (packaging structure)
    if (edgeDetection.hasEdges || edgeDetection.hasRectangularShape) {
      let edgeScore = edgeDetection.edgeConfidence;
      if (edgeDetection.hasRectangularShape) edgeScore += 20;
      totalScore += Math.min(edgeScore, 100) * 0.35;
      maxScore += 100 * 0.35;
    }
    
    // Color profile (vibrant packaging)
    if (colorDetection.hasVibrantColors) {
      totalScore += colorDetection.colorConfidence * 0.25;
      maxScore += 100 * 0.25;
    }
    
    const finalConfidence = maxScore > 0 ? Math.round((totalScore / maxScore) * 100) : 0;
    const isProduct = finalConfidence > 42; // Threshold for "product detected"
    
    const details = {
      textDetected: textDetection.hasText,
      textConfidence: textDetection.textConfidence,
      edgesDetected: edgeDetection.hasEdges,
      rectangularShape: edgeDetection.hasRectangularShape,
      vibrantColors: colorDetection.hasVibrantColors,
      overallConfidence: finalConfidence
    };
    
    return { isProduct, confidence: finalConfidence, details };
  }, []);

  // Temporal smoothing - requires multiple consistent frames
  const getSmoothedDetection = useCallback((currentDetection) => {
    frameBufferRef.current.push(currentDetection);
    if (frameBufferRef.current.length > 5) {
      frameBufferRef.current.shift();
    }
    
    if (frameBufferRef.current.length < 3) return currentDetection;
    
    // Count how many recent frames detected a product
    const productFrames = frameBufferRef.current.filter(d => d.isProduct).length;
    const isStableProduct = productFrames >= 3;
    
    // Average confidence over recent frames
    const avgConfidence = frameBufferRef.current.reduce((sum, d) => sum + d.confidence, 0) / frameBufferRef.current.length;
    
    return {
      isProduct: isStableProduct,
      confidence: Math.round(avgConfidence),
      details: currentDetection.details
    };
  }, []);

  // Main detection loop
  const detectFrame = useCallback(() => {
    const video = videoRef?.current;
    if (!video || video.paused || video.ended || video.videoWidth === 0) {
      animationRef.current = requestAnimationFrame(detectFrame);
      return;
    }

    // Throttle to every 500ms for smooth, responsive detection
    const now = Date.now();
    if (now - lastDetectionRef.current < 500) {
      animationRef.current = requestAnimationFrame(detectFrame);
      return;
    }
    lastDetectionRef.current = now;

    const rawDetection = detectProductPackaging(video);
    const smoothed = getSmoothedDetection(rawDetection);
    
    setIsProductDetected(smoothed.isProduct);
    setDetectionConfidence(smoothed.confidence);
    setDetectionDetails(smoothed.details);
    
    animationRef.current = requestAnimationFrame(detectFrame);
  }, [videoRef, detectProductPackaging, getSmoothedDetection]);

  // Start/stop detection loop
  useEffect(() => {
    if (!isActive || isAnalyzing) {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
      return;
    }
    
    lastDetectionRef.current = Date.now();
    animationRef.current = requestAnimationFrame(detectFrame);
    
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
    };
  }, [isActive, isAnalyzing, detectFrame]);

  return { 
    isProductDetected, 
    detectionConfidence, 
    isAnalyzing,
    detectionDetails,
    isModelLoading: isAnalyzing
  };
};

export default useProductDetection;