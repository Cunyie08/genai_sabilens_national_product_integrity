import React from 'react';
import Icon from '../../common/Icon';

const DetectionOverlay = ({ isProductDetected, detectionConfidence, detectedObjects, isModelLoading }) => {
  return (
    <div className="absolute inset-0 pointer-events-none">
      {/* Hidden canvas for text detection */}
      <canvas className="hidden" id="detection-canvas" />

      {/* Detection Status Badge */}
      <div className="absolute top-20 left-1/2 -translate-x-1/2 z-20">
        <div className={`px-4 py-2 rounded-full backdrop-blur-md flex items-center gap-2 transition-all shadow-lg
          ${isProductDetected 
            ? 'bg-green-500/90 text-white' 
            : isModelLoading
            ? 'bg-blue-500/90 text-white'
            : 'bg-yellow-500/90 text-white'}`}>
          <Icon 
            name={isProductDetected ? 'CheckCircle' : isModelLoading ? 'Loader' : 'AlertTriangle'} 
            size={16} 
            className={`text-white ${isModelLoading ? 'animate-spin' : ''}`}
            library="fi" 
          />
          <span className="text-sm font-medium">
            {isModelLoading 
              ? 'Loading AI Model...' 
              : isProductDetected 
                ? `Product Detected (${Math.round(detectionConfidence)}%)` 
                : 'No Product Detected'}
          </span>
        </div>
      </div>

      {/* Guidance Overlay when no product detected */}
      {!isProductDetected && !isModelLoading && detectionConfidence === 0 && (
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-10 pointer-events-auto">
          <div className="text-center max-w-xs mx-auto p-6 bg-white/95 rounded-2xl shadow-2xl">
            <div className="w-20 h-20 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Icon name="Package" size={32} className="text-yellow-600" library="fi" />
            </div>
            <h3 className="text-lg font-bold text-gray-900 mb-2">No Product Detected</h3>
            <p className="text-sm text-gray-600 mb-4">
              Please point your camera at a product label or packaging.
            </p>
            <ul className="text-left text-xs space-y-2 text-gray-500 mb-4">
              <li className="flex items-center gap-2">
                <Icon name="Check" size={12} className="text-primary" library="fi" />
                Hold product in well-lit area
              </li>
              <li className="flex items-center gap-2">
                <Icon name="Check" size={12} className="text-primary" library="fi" />
                Make sure label text is visible
              </li>
              <li className="flex items-center gap-2">
                <Icon name="Check" size={12} className="text-primary" library="fi" />
                Fill the frame with the product
              </li>
            </ul>
            <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs text-gray-400 mt-2">Scanning for products...</p>
          </div>
        </div>
      )}

      {/* Visual Guide Frame - highlights detected product region */}
      {detectedObjects.length > 0 && (
        <div className="absolute inset-0">
          {detectedObjects.map((obj, idx) => {
            const [x, y, width, height] = obj.bbox;
            return (
              <div
                key={idx}
                className="absolute border-2 border-green-500 rounded-lg animate-pulse"
                style={{
                  left: `${x}px`,
                  top: `${y}px`,
                  width: `${width}px`,
                  height: `${height}px`,
                }}
              >
                <span className="absolute -top-6 left-0 text-xs bg-green-500 text-white px-2 py-0.5 rounded">
                  {obj.class} ({Math.round(obj.score * 100)}%)
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Text Detection Indicator */}
      {!detectedObjects.length && isProductDetected && (
        <div className="absolute bottom-32 left-1/2 -translate-x-1/2 bg-black/70 backdrop-blur px-3 py-1 rounded-full">
          <span className="text-white text-xs flex items-center gap-1">
            <Icon name="FileText" size={12} className="text-green-400" library="fi" />
            Text detected - Ready to scan
          </span>
        </div>
      )}
    </div>
  );
};

export default DetectionOverlay;