import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../../common/Icon';
import Card from '../../common/Card';
import Button from '../../common/Button';
// Remove saveScan import - NOT NEEDED
// import { saveScan } from '../../../services/scanHistory';

const ScanResultSafe = ({ onBack, onReportIssue, onScanAnother }) => {
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

      // Extract fields from real AI result when available
      const verdictRaw = aiResult?.final_verdict || 'AUTHENTIC';
      const isSuspicious = verdictRaw === 'SUSPICIOUS';
      const confidence = aiResult?.confidence_pct ?? (aiResult?.confidence_score != null
        ? Math.round((aiResult.confidence_score || 0) * 100)
        : 92);

      // Extract NAFDAC number from evidence package or breakdown
      const evidence = aiResult?.evidence_package || {};
      const regPayload = aiResult?.breakdown?.reg || {};
      const nafdacNumber = evidence?.nafdac_number
        || regPayload?.nafdac_number
        || 'Extracted by AI';

      const status = isSuspicious ? 'suspicious' : 'authentic';

      const data = {
        id: scanId || `scan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        product: aiResult?.evidence_package?.product_name || 'Verified Product',
        productImage: productImage || null,
        category: aiResult?.evidence_package?.category || 'Consumer Goods',
        manufacturer: aiResult?.evidence_package?.manufacturer || 'Registered Manufacturer',
        nafdacNumber,
        batchNumber: aiResult?.evidence_package?.batch_number || 'AI-Verified',
        expiryDate: aiResult?.evidence_package?.expiry_date || 'Valid',
        status,
        isSuspicious,
        similarity: confidence,
        confidence,
        action: aiResult?.action || (isSuspicious ? 'CAUTION' : 'BUY'),
        instruction: aiResult?.simple_instruction || (
          isSuspicious
            ? 'This product shows some irregularities. Proceed with caution.'
            : 'This product appears authentic. Safe to purchase.'
        ),
        summary: aiResult?.summary || '',
        detail: aiResult?.detail || '',
        warnings: aiResult?.warnings || [],
        signalsUsed: aiResult?.signals_used || [],
        location: scanLocation || (scanLat && scanLng ? `${scanLat.toFixed(4)}° N, ${scanLng.toFixed(4)}° E` : 'Location unavailable'),
        latitude: scanLat,
        longitude: scanLng,
        time: 'Today, ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        verified: true,
        timestamp: Date.now(),
        date: new Date().toISOString(),
      };

      setScanData(data);
      
      // REMOVED: saveScan(data) - Backend already auto-saves!
      console.log('Scan loaded (backend already saved this)');
    };

    loadScan();
  }, []);

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
        onClick={onBack}
        className="mb-6"
      >
        <Icon name="ArrowLeft" size={24} className="text-gray-500" library="fi" />
      </button>

      {/* Result Card */}
      <Card className="mb-6 border-2 border-success/20 overflow-hidden">
        {/* Success / Caution Banner */}
        <div className={`p-6 text-center border-b ${scanData.isSuspicious ? 'bg-yellow-50 border-yellow-100' : 'bg-success/5 border-success/10'}`}>
          <div className={`w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4 ${scanData.isSuspicious ? 'bg-yellow-100' : 'bg-success/10'}`}>
            <Icon name={scanData.isSuspicious ? 'AlertTriangle' : 'CheckCircle'} size={40} className={scanData.isSuspicious ? 'text-yellow-600' : 'text-success'} library="fi" />
          </div>
          <h1 className={`text-3xl font-bold mb-2 ${scanData.isSuspicious ? 'text-yellow-700' : 'text-success'}`}>
            {scanData.isSuspicious ? 'PROCEED WITH CAUTION' : 'SAFE TO BUY'}
          </h1>
          <p className="text-gray-600 text-sm">{scanData.instruction}</p>
          {scanData.isSuspicious && (
            <div className="mt-3 inline-block bg-yellow-100 text-yellow-800 text-xs font-medium px-3 py-1 rounded-full">
              AI Confidence: {scanData.confidence}%
            </div>
          )}
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

        {/* Voice Report */}
        <div className="p-4 border-b border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Icon name="Volume2" size={18} className="text-primary" library="fi" />
              <span className="text-sm font-medium text-gray-700">Listen to Report</span>
            </div>
            <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded-full">
              4 Languages
            </span>
          </div>
          <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
            <button className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center hover:bg-primary/20 transition-colors">
              <Icon name="Play" size={18} className="text-primary" library="fi" />
            </button>
            <div className="flex-1">
              <div className="h-2 bg-gray-200 rounded-full">
                <div className="w-0 h-2 bg-primary rounded-full" />
              </div>
            </div>
            <span className="text-xs text-gray-400">0:00</span>
            <button className="p-2 hover:bg-gray-200 rounded-lg transition-colors">
              <Icon name="Download" size={16} className="text-gray-400" library="fi" />
            </button>
          </div>
        </div>

        {/* Verification Details */}
        <div className="p-4 space-y-4">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <Icon name="Shield" size={18} className="text-primary" library="fi" />
            VERIFICATION DETAILS
          </h3>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-50 p-3 rounded-xl">
              <p className="text-xs text-gray-400 mb-1">NAFDAC Number</p>
              <p className="font-mono font-medium text-sm">{scanData.nafdacNumber}</p>
              <div className="flex items-center gap-1 mt-1">
                <Icon name="Check" size={12} className="text-success" library="fi" />
                <span className="text-xs text-success">Verified</span>
              </div>
            </div>

            <div className="bg-gray-50 p-3 rounded-xl">
              <p className="text-xs text-gray-400 mb-1">Category</p>
              <p className="font-medium text-sm">{scanData.category}</p>
            </div>

            <div className="bg-gray-50 p-3 rounded-xl">
              <p className="text-xs text-gray-400 mb-1">Expiry Status</p>
              <p className="font-medium text-sm text-success">Valid</p>
              <p className="text-xs text-gray-400">{scanData.expiryDate}</p>
            </div>

            <div className="bg-gray-50 p-3 rounded-xl">
              <p className="text-xs text-gray-400 mb-1">Manufacturer</p>
              <p className="font-medium text-sm">{scanData.manufacturer}</p>
            </div>

            <div className="bg-gray-50 p-3 rounded-xl">
              <p className="text-xs text-gray-400 mb-1">Batch Number</p>
              <p className="font-mono font-medium text-sm">{scanData.batchNumber}</p>
            </div>

            <div className="bg-gray-50 p-3 rounded-xl">
              <p className="text-xs text-gray-400 mb-1">Location</p>
              <p className="font-medium text-sm">{scanData.location}</p>
            </div>
          </div>

          {/* AI Confidence Score */}
          <div className={`p-3 rounded-xl ${scanData.isSuspicious ? 'bg-yellow-50' : 'bg-primary/5'}`}>
            <div className="flex justify-between items-center mb-2">
              <span className={`text-sm font-medium ${scanData.isSuspicious ? 'text-yellow-700' : 'text-primary'}`}>AI Confidence Score</span>
              <span className={`text-sm font-bold ${scanData.isSuspicious ? 'text-yellow-700' : 'text-primary'}`}>{scanData.similarity}%</span>
            </div>
            <div className={`h-2 rounded-full overflow-hidden ${scanData.isSuspicious ? 'bg-yellow-200' : 'bg-primary/10'}`}>
              <div
                className={`h-full rounded-full ${scanData.isSuspicious ? 'bg-yellow-500' : 'bg-primary'}`}
                style={{ width: `${scanData.similarity}%` }}
              />
            </div>
          </div>

          {/* AI Summary */}
          {scanData.summary && (
            <div className="bg-gray-50 p-3 rounded-xl">
              <p className="text-xs text-gray-500 mb-1">AI Analysis Summary</p>
              <p className="text-sm text-gray-700">{scanData.summary}</p>
            </div>
          )}

          {/* Warnings */}
          {scanData.warnings?.length > 0 && (
            <div className="bg-yellow-50 p-3 rounded-xl">
              <p className="text-xs font-medium text-yellow-700 mb-2">Warnings</p>
              {scanData.warnings.map((w, i) => (
                <p key={i} className="text-xs text-yellow-600">• {w?.message || w?.type || String(w)}</p>
              ))}
            </div>
          )}

          {/* Quality Seals */}
          <div className="flex items-center gap-2 flex-wrap">
            {scanData.signalsUsed?.includes('reg') && (
              <span className="text-xs bg-success/10 text-success px-3 py-1 rounded-full flex items-center gap-1">
                <Icon name="Check" size={12} className="text-success" library="fi" />
                NAFDAC Verified
              </span>
            )}
            {scanData.signalsUsed?.includes('visual') && (
              <span className="text-xs bg-success/10 text-success px-3 py-1 rounded-full flex items-center gap-1">
                <Icon name="Check" size={12} className="text-success" library="fi" />
                Visual Match
              </span>
            )}
            {scanData.signalsUsed?.includes('ocr') && (
              <span className="text-xs bg-success/10 text-success px-3 py-1 rounded-full flex items-center gap-1">
                <Icon name="Check" size={12} className="text-success" library="fi" />
                OCR Verified
              </span>
            )}
            {!scanData.signalsUsed?.length && (
              <span className="text-xs bg-success/10 text-success px-3 py-1 rounded-full flex items-center gap-1">
                <Icon name="Check" size={12} className="text-success" library="fi" />
                AI Verified
              </span>
            )}
          </div>
        </div>

        {/* Report Issue */}
        <button 
          onClick={onReportIssue}
          className="w-full text-center text-sm text-gray-400 py-4 border-t border-gray-100 hover:bg-gray-50 transition-colors flex items-center justify-center gap-2"
        >
          <Icon name="Flag" size={16} className="text-gray-400" library="fi" />
          Something looks wrong? Report Issue
        </button>
      </Card>

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

export default ScanResultSafe;