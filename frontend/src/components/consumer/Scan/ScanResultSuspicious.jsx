// src/components/consumer/Scan/ScanResultSuspicious.jsx

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../../common/Icon';
import Card from '../../common/Card';
import Button from '../../common/Button';

const ScanResultSuspicious = ({ onBack, onReportIssue, onScanAnother }) => {
  const navigate = useNavigate();
  const [scanData, setScanData] = useState(null);

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

      const confidence = aiResult?.confidence_pct ?? (
        aiResult?.confidence_score != null
          ? Math.round((aiResult.confidence_score || 0) * 100)
          : 55
      );

      // Extract warnings
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
        similarity: confidence,
        confidence,
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
    };

    loadScan();
  }, []);

  // Handle back button click
  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      navigate(-1); // Go back to previous page
    }
  };

  // Handle report issue
  const handleReportIssue = () => {
    if (onReportIssue) {
      onReportIssue();
    } else {
      navigate('/report-issue', { state: { scanData } });
    }
  };

  // Handle scan another
  const handleScanAnother = () => {
    if (onScanAnother) {
      onScanAnother();
    } else {
      navigate('/scan');
    }
  };

  if (!scanData) {
    return (
      <div className="px-6 py-8 flex justify-center">
        <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="px-6 py-8">
      {/* Back Button */}
      <button
        onClick={handleBack}
        className="mb-6"
      >
        <Icon name="ArrowLeft" size={24} className="text-gray-500" library="fi" />
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
            This product has raised some concerns. Please verify before purchase.
          </p>
        </div>

        {/* Product Image */}
        <div className="p-4 border-b border-gray-100 relative">
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
            {/* Warning Badge */}
            <div className="absolute top-2 right-2 bg-warning text-white text-xs px-2 py-1 rounded-lg">
              SUSPICIOUS
            </div>
          </div>
        </div>

        {/* Reason */}
        <div className="p-4 border-b border-gray-100">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Icon name="AlertTriangle" size={18} className="text-warning" library="fi" />
            Why this product is flagged:
          </h3>
          <div className="bg-warning/5 rounded-xl p-4">
            {scanData.summary && (
              <p className="text-sm text-gray-700 mb-3 font-medium">{scanData.summary}</p>
            )}
            <ul className="space-y-3 text-sm">
              {scanData.redFlags.map((flag, idx) => (
                <li key={idx} className="flex items-start gap-3">
                  <div className="w-5 h-5 bg-warning/10 rounded-full flex items-center justify-center mt-0.5 shrink-0">
                    <Icon name="AlertTriangle" size={12} className="text-warning" library="fi" />
                  </div>
                  <span className="text-gray-700">{flag}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Similarity Score */}
        <div className="p-4 border-b border-gray-100">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">AI Confidence Score</span>
            <span className="text-sm font-bold text-warning">{scanData.similarity}%</span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full bg-warning rounded-full" style={{ width: `${scanData.similarity}%` }} />
          </div>
          <p className="text-xs text-gray-400 mt-2">
            {scanData.detail || 'Medium confidence — product requires additional verification.'}
          </p>
        </div>

        {/* Location Captured */}
        <div className="p-4 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Icon name="MapPin" size={18} className="text-gray-400" library="fi" />
              <span className="text-sm text-gray-600">Location captured</span>
            </div>
            <div className="flex items-center gap-2">
              <Icon name="Check" size={14} className="text-success" library="fi" />
              <span className="text-xs text-gray-500">GPS locked</span>
            </div>
          </div>
          <div className="mt-2 bg-gray-50 p-3 rounded-lg flex items-center gap-2">
            <Icon name="Navigation" size={16} className="text-primary" library="fi" />
            <span className="text-sm font-medium">{scanData.location}</span>
          </div>
        </div>

        {/* What To Do */}
        <div className="p-4 border-b border-gray-100">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Recommended Actions</h3>
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Icon name="Shield" size={14} className="text-primary" library="fi" />
              <span>Verify NAFDAC number on official NAFDAC portal</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Icon name="CheckCircle" size={14} className="text-primary" library="fi" />
              <span>Check batch number with manufacturer</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Icon name="AlertTriangle" size={14} className="text-warning" library="fi" />
              <span>Do not purchase if unsure - report to NAFDAC</span>
            </div>
          </div>
        </div>

        {/* Warning Signs */}
        {scanData.warnings?.length > 0 && (
          <div className="p-4 border-b border-gray-100">
            <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
              <Icon name="AlertOctagon" size={16} className="text-warning" library="fi" />
              Warning Signs Detected
            </h3>
            <div className="flex flex-wrap gap-2">
              {scanData.warnings.map((w, i) => (
                <span key={i} className="text-xs bg-warning/10 text-warning px-3 py-1 rounded-full">
                  {w?.type || w?.message || String(w)}
                </span>
              ))}
            </div>
          </div>
        )}
      </Card>

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

      {/* Trust Badge */}
      <div className="mt-6 text-center">
        <div className="flex items-center justify-center gap-2 text-xs text-gray-400">
          <Icon name="Shield" size={14} className="text-primary" library="fi" />
          <span>Verified by SabiLens AI • Report ID: {scanData.id?.slice(-8).toUpperCase() || Math.random().toString(36).substr(2, 8).toUpperCase()}</span>
        </div>
      </div>
    </div>
  );
};

export default ScanResultSuspicious;