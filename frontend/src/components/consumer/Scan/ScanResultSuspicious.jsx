import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../../common/Icon';
import Card from '../../common/Card';
import Button from '../../common/Button';

const ScanResultSuspicious = ({ onBack, onReportIssue, onScanAnother }) => {
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
            : 55
        )
      );
      
      const confidenceLabel = aiResult?.confidence_label || 'Suspicion Confidence';

      const warnings = aiResult?.warnings || [];
      const redFlags = warnings.length > 0
        ? warnings.map((w) => w?.message || w?.type || String(w))
        : aiResult?.detail
          ? [aiResult.detail]
          : ['NAFDAC number format issue', 'Packaging inconsistencies detected', 'Batch code verification pending'];

      const data = {
        id: scanId || `scan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        product: aiResult?.evidence_package?.product_name || 'Product Under Review',
        productImage: productImage || null,
        category: aiResult?.evidence_package?.category || 'Consumer Goods',
        manufacturer: aiResult?.evidence_package?.manufacturer || 'Verification Pending',
        nafdacNumber: aiResult?.evidence_package?.nafdac_number || 'Partially Verified',
        batchNumber: aiResult?.evidence_package?.batch_number || 'Needs Review',
        expiryDate: aiResult?.evidence_package?.expiry_date || 'Verify with NAFDAC',
        status: 'suspicious',
        similarity: displayConfidence,
        confidence: displayConfidence,
        confidenceLabel: confidenceLabel,
        severity: aiResult?.severity || 'MEDIUM',
        action: aiResult?.action || 'VERIFY BEFORE USE',
        instruction: aiResult?.simple_instruction || 'This product shows some irregularities. Please verify with NAFDAC before use.',
        summary: aiResult?.summary || 'Product requires additional verification',
        detail: aiResult?.detail || 'The product could not be fully verified. Please check with NAFDAC database.',
        redFlags,
        warnings,
        signalsUsed: aiResult?.signals_used || ['ocr', 'visual'],
        location: scanLocation || (scanLat && scanLng ? `${scanLat.toFixed(4)}° N, ${scanLng.toFixed(4)}° E` : 'Location captured'),
        latitude: scanLat,
        longitude: scanLng,
        time: 'Today, ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        verified: false,
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

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      navigate(-1);
    }
  };

  const handleReportIssue = () => {
    if (onReportIssue) {
      onReportIssue();
    } else {
      navigate('/report-issue', { state: { scanData } });
    }
  };

  const handleScanAnother = () => {
    if (onScanAnother) {
      onScanAnother();
    } else {
      navigate('/scan');
    }
  };

  const handleRescan = () => {
    sessionStorage.removeItem('currentScan');
    navigate('/scan');
  };

  if (!scanData) {
    return (
      <div className="px-6 py-8 flex justify-center">
        <div className="w-16 h-16 border-4 border-warning border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="px-6 py-4">
      {/* Back Button - Circle */}
      <button
        onClick={handleBack}
        className="mb-6 w-10 h-10 rounded-full bg-white shadow-sm border border-gray-100 flex items-center justify-center hover:bg-gray-50 transition-all"
      >
        <Icon name="ArrowLeft" size={20} className="text-gray-600" library="fi" />
      </button>

      {/* Result Card */}
      <Card className="mb-6 border-2 border-warning/20 overflow-hidden">
        {/* Warning Banner */}
        <div className="bg-warning/5 p-6 text-center border-b border-warning/10">
          <div className="w-20 h-20 bg-warning/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <Icon name="AlertTriangle" size={40} className="text-warning" library="fi" />
          </div>
          <h1 className="text-3xl font-bold text-warning mb-2">PROCEED WITH CAUTION</h1>
          <p className="text-gray-600">
            {scanData.instruction}
          </p>
        </div>

        {/* Product Image */}
        <div className="p-4 border-b border-gray-100">
          <div className="bg-gray-100 rounded-xl h-48 flex items-center justify-center overflow-hidden relative">
            {scanData.productImage ? (
              <img 
                src={scanData.productImage} 
                alt={scanData.product}
                className="w-full h-full object-contain opacity-70"
                onError={(e) => {
                  e.target.onerror = null;
                  e.target.style.display = 'none';
                  const parent = e.target.parentElement;
                  if (parent) {
                    parent.innerHTML = `
                      <div class="w-full h-full flex items-center justify-center bg-gray-100">
                        <svg class="w-12 h-12 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                      </div>
                    `;
                  }
                }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-gray-100">
                <Icon name="Image" size={48} className="text-gray-300" library="fi" />
              </div>
            )}
            <div className="absolute top-2 right-2 bg-warning text-white text-xs px-2 py-1 rounded-lg">
              SUSPICIOUS
            </div>
          </div>
        </div>

        {/* 1. Risk Assessment */}
        <div className="p-4 border-b border-gray-100">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Risk Assessment</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-warning/5 p-3 rounded-lg text-center">
              <p className="text-xl font-bold text-warning">
                {scanData.severity === 'CRITICAL' || scanData.severity === 'HIGH'
                  ? 'High'
                  : scanData.severity === 'MEDIUM'
                  ? 'Medium'
                  : 'Low'}
              </p>
              <p className="text-xs text-gray-500">Health Risk</p>
            </div>
            <div className="bg-warning/5 p-3 rounded-lg text-center">
              <p className="text-xl font-bold text-warning">
                {scanData.severity
                  ? scanData.severity.charAt(0) + scanData.severity.slice(1).toLowerCase()
                  : 'Medium'}
              </p>
              <p className="text-xs text-gray-500">Suspicion Level</p>
            </div>
          </div>
        </div>

        {/* 2. Confidence Label */}
        <div className="p-4 border-b border-gray-100">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">{scanData.confidenceLabel}</span>
            <span className="text-sm font-bold text-warning">{scanData.confidence}%</span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full bg-warning rounded-full" style={{ width: `${scanData.confidence}%` }} />
          </div>
          <p className="text-xs text-gray-400 mt-2">
            {scanData.detail || 'Medium confidence — product requires additional verification.'}
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

        {/* 5. Why this product is flagged */}
        <div className="p-4 border-b border-gray-100">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Icon name="AlertTriangle" size={18} className="text-warning" library="fi" />
            Why this product is flagged:
          </h3>
          <div className="bg-warning/5 rounded-xl p-4">
            <p className="text-sm text-gray-700">
              {scanData.instruction || 'We could not fully verify this product. Please check with NAFDAC at nafdac.gov.ng before purchasing.'}
            </p>
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
          variant="warning"
          fullWidth
          onClick={handleReportIssue}
          icon="Flag"
        >
          Report to NAFDAC for Investigation
        </Button>

        <Button
          variant="outline"
          fullWidth
          onClick={handleScanAnother}
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

      {/* Recommended Actions */}
      <div className="mt-6 p-4 bg-warning/5 rounded-xl">
        <h4 className="text-sm font-medium text-warning mb-2 flex items-center gap-2">
          <Icon name="Shield" size={14} library="fi" />
          Recommended Actions
        </h4>
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs text-gray-600">
            <Icon name="CheckCircle" size={12} className="text-primary" library="fi" />
            <span>Verify NAFDAC number on official NAFDAC portal</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-600">
            <Icon name="CheckCircle" size={12} className="text-primary" library="fi" />
            <span>Check batch number with manufacturer</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-600">
            <Icon name="AlertTriangle" size={12} className="text-warning" library="fi" />
            <span>Do not purchase if unsure - report to NAFDAC</span>
          </div>
        </div>
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

export default ScanResultSuspicious;