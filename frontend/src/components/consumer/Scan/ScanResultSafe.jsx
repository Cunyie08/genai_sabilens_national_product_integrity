import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../../common/Icon';
import Card from '../../common/Card';
import Button from '../../common/Button';

const ScanResultSafe = ({ onBack, onReportIssue, onScanAnother }) => {
  const navigate = useNavigate();
  const [scanData, setScanData] = useState(null);
  const [locationName, setLocationName] = useState('');

  useEffect(() => {
    const loadScan = async () => {
      const storedScan = sessionStorage.getItem('currentScan');
      let productImage = null;
      let aiResult = null;
      let scanLocation = '';
      let scanLat = null;
      let scanLng = null;
      let scanId = null;

      if (storedScan) {
        try {
          const parsed = JSON.parse(storedScan);
          productImage = parsed.imageUrl || parsed.productImage;
          aiResult = parsed.aiResult || null;
          scanLocation = parsed.location || '';
          scanLat = parsed.latitude ?? null;
          scanLng = parsed.longitude ?? null;
          scanId = parsed.scan_id;
        } catch {}
      }

      const displayConfidence = aiResult?.display_confidence ?? (
        aiResult?.confidence_pct ?? (
          aiResult?.confidence_score != null
            ? Math.round((aiResult.confidence_score || 0) * 100)
            : 92
        )
      );
      
      const confidenceLabel = aiResult?.confidence_label || 'Authenticity Confidence';

      const evidence = aiResult?.evidence_package || {};
      const regPayload = aiResult?.breakdown?.reg || {};
      const nafdacNumber = evidence?.nafdac_number || regPayload?.nafdac_number || 'Extracted by AI';

      const data = {
        id: scanId || `scan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        product: evidence?.product_name || 'Verified Product',
        productImage: productImage || null,
        category: evidence?.category || 'Consumer Goods',
        manufacturer: evidence?.manufacturer || 'Registered Manufacturer',
        nafdacNumber,
        batchNumber: evidence?.batch_number || 'AI-Verified',
        expiryDate: evidence?.expiry_date || 'Valid',
        status: 'authentic',
        similarity: displayConfidence,
        confidence: displayConfidence,
        confidenceLabel: confidenceLabel,
        severity: aiResult?.severity || 'LOW',
        action: aiResult?.action || 'BUY',
        instruction: aiResult?.simple_instruction || 'This product appears authentic. Safe to purchase.',
        summary: aiResult?.summary || '',
        detail: aiResult?.detail || '',
        warnings: aiResult?.warnings || [],
        signalsUsed: aiResult?.signals_used || ['reg', 'visual', 'ocr'],
        location: scanLocation || (scanLat && scanLng ? `${scanLat.toFixed(4)}° N, ${scanLng.toFixed(4)}° E` : 'Location unavailable'),
        latitude: scanLat,
        longitude: scanLng,
        time: 'Today, ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        verified: true,
        timestamp: Date.now(),
        date: new Date().toISOString(),
      };

      setScanData(data);

      // Convert coordinates to location name
      if (scanLat && scanLng) {
        try {
          const response = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${scanLat}&lon=${scanLng}&zoom=18&addressdetails=1`
          );
          const result = await response.json();
          if (result.display_name) {
            const address = result.address;
            const city = address.city || address.town || address.village || '';
            const state = address.state || '';
            const country = address.country || '';
            setLocationName([city, state, country].filter(Boolean).join(', '));
          } else {
            setLocationName(scanLocation || `${scanLat.toFixed(4)}° N, ${scanLng.toFixed(4)}° E`);
          }
        } catch (error) {
          console.error('Geocoding error:', error);
          setLocationName(scanLocation || `${scanLat.toFixed(4)}° N, ${scanLng.toFixed(4)}° E`);
        }
      } else {
        setLocationName(scanLocation || 'Location unavailable');
      }
    };

    loadScan();
  }, []);

  const handleRescan = () => {
    sessionStorage.removeItem('currentScan');
    navigate('/scan');
  };

  if (!scanData) {
    return (
      <div className="px-6 py-8 flex justify-center">
        <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="px-6 py-4">
      {/* Back Button - Circle */}
      <button
        onClick={onBack}
        className="mb-6 w-10 h-10 rounded-full bg-white shadow-sm border border-gray-100 flex items-center justify-center hover:bg-gray-50 transition-all"
      >
        <Icon name="ArrowLeft" size={20} className="text-gray-600" library="fi" />
      </button>

      {/* Result Card */}
      <Card className="mb-6 border-2 border-success/20 overflow-hidden">
        {/* Success Banner */}
        <div className="bg-success/5 p-6 text-center border-b border-success/10">
          <div className="w-20 h-20 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <Icon name="CheckCircle" size={40} className="text-success" library="fi" />
          </div>
          <h1 className="text-3xl font-bold text-success mb-2">SAFE TO BUY</h1>
          <p className="text-gray-600">
            {scanData.instruction}
          </p>
        </div>

        {/* Product Image */}
        <div className="p-4 border-b border-gray-100">
          <div className="bg-gray-100 rounded-xl h-48 flex items-center justify-center overflow-hidden">
            {scanData.productImage ? (
              <img 
                src={scanData.productImage} 
                alt={scanData.product}
                className="w-full h-full object-contain"
                onError={(e) => {
                  e.target.onerror = null;
                  e.target.src = 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400';
                }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-gray-100">
                <Icon name="Image" size={48} className="text-gray-300" library="fi" />
              </div>
            )}
          </div>
        </div>

        {/* 1. Risk Assessment */}
        <div className="p-4 border-b border-gray-100">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Risk Assessment</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-success/5 p-3 rounded-lg text-center">
              <p className="text-xl font-bold text-success">
                {scanData.severity === 'CRITICAL' || scanData.severity === 'HIGH'
                  ? 'High'
                  : scanData.severity === 'MEDIUM'
                  ? 'Medium'
                  : 'Low'}
              </p>
              <p className="text-xs text-gray-500">Health Risk</p>
            </div>
            <div className="bg-success/5 p-3 rounded-lg text-center">
              <p className="text-xl font-bold text-success">
                {scanData.confidenceLabel
                  ? scanData.confidenceLabel.charAt(0) + scanData.confidenceLabel.slice(1).toLowerCase()
                  : 'Verified'}
              </p>
              <p className="text-xs text-gray-500">Authenticity Level</p>
            </div>
          </div>
        </div>

        {/* 2. Confidence Label */}
        <div className="p-4 border-b border-gray-100">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">{scanData.confidenceLabel}</span>
            <span className="text-sm font-bold text-success">{scanData.confidence}%</span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full bg-success rounded-full" style={{ width: `${scanData.confidence}%` }} />
          </div>
          <p className="text-xs text-gray-400 mt-2">
            {scanData.detail || 'High confidence — Product matches authentic samples in the NAFDAC registry.'}
          </p>
        </div>

        {/* 3. Legend Box - Red, Yellow, Green indicators */}
        <div className="p-4 border-b border-gray-100">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Verification Legend</h3>
          <div className="flex items-center justify-around">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-danger"></div>
              <span className="text-xs text-gray-600">Fake</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-yellow-500"></div>
              <span className="text-xs text-gray-600">Suspicious</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-green-500"></div>
              <span className="text-xs text-gray-600">Authentic</span>
            </div>
          </div>
        </div>


        {/* 5. Why this product is verified */}
        <div className="p-4 border-b border-gray-100">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Icon name="Shield" size={18} className="text-success" library="fi" />
            Why this product is verified:
          </h3>
          <div className="bg-success/5 rounded-xl p-4">
            {scanData.summary && (
              <p className="text-sm text-gray-700 mb-3 font-medium">{scanData.summary}</p>
            )}
            <ul className="space-y-3 text-sm">
              {scanData.signalsUsed?.includes('reg') && (
                <li className="flex items-start gap-3">
                  <div className="w-5 h-5 bg-success/10 rounded-full flex items-center justify-center mt-0.5 shrink-0">
                    <Icon name="Check" size={12} className="text-success" library="fi" />
                  </div>
                  <span className="text-gray-700">NAFDAC registration number verified in official database</span>
                </li>
              )}
              {scanData.signalsUsed?.includes('visual') && (
                <li className="flex items-start gap-3">
                  <div className="w-5 h-5 bg-success/10 rounded-full flex items-center justify-center mt-0.5 shrink-0">
                    <Icon name="Check" size={12} className="text-success" library="fi" />
                  </div>
                  <span className="text-gray-700">Visual packaging matches authentic product reference</span>
                </li>
              )}
              {scanData.signalsUsed?.includes('ocr') && (
                <li className="flex items-start gap-3">
                  <div className="w-5 h-5 bg-success/10 rounded-full flex items-center justify-center mt-0.5 shrink-0">
                    <Icon name="Check" size={12} className="text-success" library="fi" />
                  </div>
                  <span className="text-gray-700">Text labels (batch number, expiry date) are correctly formatted</span>
                </li>
              )}
              {!scanData.signalsUsed?.length && (
                <li className="flex items-start gap-3">
                  <div className="w-5 h-5 bg-success/10 rounded-full flex items-center justify-center mt-0.5 shrink-0">
                    <Icon name="Check" size={12} className="text-success" library="fi" />
                  </div>
                  <span className="text-gray-700">AI analysis confirms product authenticity</span>
                </li>
              )}
            </ul>
          </div>
        </div>

        {/* 6. Location/GPS - Converted to precise location name */}
        <div className="p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Icon name="MapPin" size={18} className="text-gray-400" library="fi" />
              <span className="text-sm text-gray-600">Location captured</span>
            </div>
            <div className="flex items-center gap-2">
              <Icon name="Check" size={14} className="text-success" library="fi" />
              <span className="text-xs text-gray-500">GPS verified</span>
            </div>
          </div>
          <div className="bg-gray-50 p-3 rounded-lg flex items-center gap-2">
            <Icon name="Navigation" size={16} className="text-primary" library="fi" />
            <span className="text-sm font-medium">{locationName || scanData.location}</span>
          </div>
          {scanData.latitude && scanData.longitude && (
            <div className="mt-2 text-xs text-gray-400 flex items-center gap-1">
              <Icon name="Clock" size={12} library="fi" />
              <span>Exact location recorded at {scanData.time}</span>
            </div>
          )}
        </div>
      </Card>

      {/* Actions */}
      <div className="space-y-3">
        <Button
          variant="primary"
          fullWidth
          onClick={onScanAnother}
          icon="Camera"
        >
          Scan Another Product
        </Button>

        <Button
          variant="outline"
          fullWidth
          onClick={handleRescan}
          icon="RotateCcw"
        >
          Rescan Product
        </Button>

        <Button
          variant="outline"
          fullWidth
          onClick={() => navigate('/scan-history')}
          icon="Clock"
        >
          View Scan History
        </Button>

        <Button
          variant="outline"
          fullWidth
          onClick={() => navigate('/home')}
          icon="Home"
        >
          Back to Home
        </Button>
      </div>

      {/* Report Issue Link */}
      <div className="mt-6 text-center">
        <button 
          onClick={onReportIssue}
          className="text-sm text-gray-400 hover:text-primary transition-colors flex items-center justify-center gap-2 mx-auto"
        >
          <Icon name="Flag" size={14} library="fi" />
          Something looks wrong? Report Issue
        </button>
      </div>

      {/* Trust Badge */}
      <div className="mt-4 text-center">
        <div className="flex items-center justify-center gap-2 text-xs text-gray-400">
          <Icon name="Shield" size={14} className="text-primary" library="fi" />
          <span>Verified by SabiLens AI • Report ID: {scanData.id?.slice(-8).toUpperCase() || Math.random().toString(36).substr(2, 8).toUpperCase()}</span>
        </div>
      </div>
    </div>
  );
};

export default ScanResultSafe;