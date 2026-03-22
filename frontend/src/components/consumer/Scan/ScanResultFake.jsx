import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../../common/Icon';
import Card from '../../common/Card';
import Button from '../../common/Button';
import Modal from '../../common/Modal';
import { saveScanToHistory, getProductImage } from '../../../services/scanHistory';

const ScanResultFake = ({ onBack, onReportToAuthority }) => {
  const navigate = useNavigate();
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportSubmitted, setReportSubmitted] = useState(false);
  const [scanData, setScanData] = useState(null);

  useEffect(() => {
    const storedScan = sessionStorage.getItem('currentScan');
    let productImage = null;
    let aiResult = null;
    let scanLocation = '';
    let scanLat = null;
    let scanLng = null;

    if (storedScan) {
      try {
        const parsed = JSON.parse(storedScan);
        productImage = parsed.imageUrl || parsed.productImage;
        aiResult = parsed.aiResult || null;
        scanLocation = parsed.location || '';
        scanLat = parsed.latitude ?? null;
        scanLng = parsed.longitude ?? null;
      } catch {}
    }

    const confidence = aiResult?.confidence_pct ?? (
      aiResult?.confidence_score != null
        ? Math.round((aiResult.confidence_score || 0) * 100)
        : 18
    );

    // Extract issues from AI warnings or evidence
    const warnings = aiResult?.warnings || [];
    const issues = warnings.length > 0
      ? warnings.map((w) => w?.message || w?.type || String(w))
      : aiResult?.detail
        ? [aiResult.detail]
        : ['Product did not match NAFDAC registry', 'Packaging anomalies detected'];

    const data = {
      product: aiResult?.evidence_package?.product_name || 'Unregistered Product',
      productImage: productImage || 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400',
      category: aiResult?.evidence_package?.category || 'Unknown',
      manufacturer: 'Unknown / Unregistered',
      nafdacNumber: 'Not Found',
      batchNumber: 'Invalid',
      status: 'fake',
      similarity: confidence,
      confidence,
      severity: aiResult?.severity || 'CRITICAL',
      action: aiResult?.action || 'DO NOT BUY',
      instruction: aiResult?.simple_instruction || 'Do not buy this product. It appears to be counterfeit.',
      summary: aiResult?.summary || '',
      detail: aiResult?.detail || '',
      issues,
      warnings,
      location: scanLocation || (scanLat && scanLng ? `${scanLat.toFixed(4)}° N, ${scanLng.toFixed(4)}° E` : 'Location unavailable'),
      latitude: scanLat,
      longitude: scanLng,
      time: 'Today, ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      verified: false,
      timestamp: new Date().toISOString(),
    };

    setScanData(data);
    saveScanToHistory(data);
  }, []);

  const handleReportSubmit = () => {
    setReportSubmitted(true);
    setTimeout(() => {
      setShowReportModal(false);
      setReportSubmitted(false);
      if (onReportToAuthority) {
        onReportToAuthority();
      }
    }, 2000);
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
        onClick={onBack}
        className="mb-6"
      >
        <Icon name="ArrowLeft" size={24} className="text-gray-500" library="fi" />
      </button>

      {/* Result Card */}
      <Card className="mb-6 border-2 border-danger/20 overflow-hidden">
        {/* Danger Banner */}
        <div className="bg-danger/5 p-6 text-center border-b border-danger/10">
          <div className="w-20 h-20 bg-danger/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <Icon name="AlertTriangle" size={40} className="text-danger" library="fi" />
          </div>
          <h1 className="text-3xl font-bold text-danger mb-2">DO NOT BUY</h1>
          <p className="text-gray-600">
            This product has been flagged as counterfeit. Using it may be harmful to your health.
          </p>
        </div>

        {/* Product Image with Warning Overlay */}
        <div className="p-4 border-b border-gray-100 relative">
          <div className="bg-gray-100 rounded-xl h-48 flex items-center justify-center overflow-hidden relative">
            <img 
              src={scanData.productImage} 
              alt={scanData.product}
              className="w-full h-full object-contain opacity-50"
              onError={(e) => {
                e.target.onerror = null;
                e.target.src = 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400';
              }}
            />
            {/* Warning Overlay */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="bg-danger/80 text-white px-4 py-2 rounded-full font-bold text-lg rotate-[-15deg]">
                COUNTERFEIT
              </div>
            </div>
            <div className="absolute top-2 right-2 bg-danger text-white text-xs px-2 py-1 rounded-lg">
              FAKE
            </div>
          </div>
        </div>

        {/* Reason */}
        <div className="p-4 border-b border-gray-100">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Icon name="XCircle" size={18} className="text-danger" library="fi" />
            Why this product is flagged:
          </h3>
          <div className="bg-danger/5 rounded-xl p-4">
            {scanData.summary && (
              <p className="text-sm text-gray-700 mb-3 font-medium">{scanData.summary}</p>
            )}
            <ul className="space-y-3 text-sm">
              {scanData.issues.map((issue, idx) => (
                <li key={idx} className="flex items-start gap-3">
                  <div className="w-5 h-5 bg-danger/10 rounded-full flex items-center justify-center mt-0.5 shrink-0">
                    <Icon name="X" size={12} className="text-danger" library="fi" />
                  </div>
                  <span className="text-gray-700">{issue}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Similarity Score */}
        <div className="p-4 border-b border-gray-100">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">AI Confidence Score</span>
            <span className="text-sm font-bold text-danger">{scanData.similarity}%</span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full bg-danger rounded-full" style={{ width: `${scanData.similarity}%` }} />
          </div>
          <p className="text-xs text-gray-400 mt-2">
            {scanData.detail || 'Low confidence — product does not match authentic samples in the NAFDAC registry.'}
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
          {scanData.latitude && scanData.longitude ? (
            <div className="mt-2 text-xs text-gray-400 flex items-center gap-1">
              <Icon name="Clock" size={12} library="fi" />
              <span>Coordinates: {scanData.latitude.toFixed(5)}° N, {scanData.longitude.toFixed(5)}° E • Exact location recorded</span>
            </div>
          ) : null}
        </div>

        {/* Risk Factors */}
        <div className="p-4 border-b border-gray-100">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Risk Assessment</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-danger/5 p-3 rounded-lg text-center">
              <p className="text-xl font-bold text-danger">High</p>
              <p className="text-xs text-gray-500">Health Risk</p>
            </div>
            <div className="bg-danger/5 p-3 rounded-lg text-center">
              <p className="text-xl font-bold text-danger">Critical</p>
              <p className="text-xs text-gray-500">Counterfeit Level</p>
            </div>
          </div>
        </div>

        {/* Warning Signs — derived from actual AI signals */}
        {scanData.warnings?.length > 0 && (
          <div className="p-4 border-b border-gray-100">
            <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
              <Icon name="AlertOctagon" size={16} className="text-danger" library="fi" />
              Warning Signs Detected
            </h3>
            <div className="flex flex-wrap gap-2">
              {scanData.warnings.map((w, i) => (
                <span key={i} className="text-xs bg-danger/10 text-danger px-3 py-1 rounded-full">
                  {w?.type || w?.message || String(w)}
                </span>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Actions */}
      <div className="space-y-3">
        <Button 
          variant="danger" 
          fullWidth
          onClick={() => setShowReportModal(true)}
          icon="Flag"
        >
          Report to NAFDAC
        </Button>
        
        <Button 
          variant="outline" 
          fullWidth 
          icon="Upload"
          onClick={() => {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'image/*';
            input.multiple = true;
            input.click();
          }}
        >
          Upload Receipt as Evidence
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

      {/* Report Modal */}
      <Modal
        isOpen={showReportModal}
        onClose={() => !reportSubmitted && setShowReportModal(false)}
        type={reportSubmitted ? 'success' : 'warning'}
        title={reportSubmitted ? 'Report Submitted' : 'Report Counterfeit Product'}
        message={
          reportSubmitted ? (
            <div className="text-center">
              <div className="w-20 h-20 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <Icon name="CheckCircle" size={40} className="text-success" library="fi" />
              </div>
              <p className="text-gray-600 mb-2">
                Thank you for helping keep our community safe.
              </p>
              <p className="text-sm text-gray-500">
                Report ID: NAFDAC-{Math.random().toString(36).substr(2, 9).toUpperCase()}
              </p>
              <p className="text-xs text-gray-400 mt-4">
                Authorities have been notified. You can track this report in your profile.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-gray-600">
                You are about to report a counterfeit product to NAFDAC. Please provide additional details:
              </p>
              
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Seller Information</label>
                  <input
                    type="text"
                    placeholder="Shop name or vendor description"
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Price Paid</label>
                  <input
                    type="text"
                    placeholder="₦"
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Additional Comments</label>
                  <textarea
                    placeholder="Any other details that might help..."
                    rows="3"
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    className="mt-1 w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary"
                  />
                  <span className="text-xs text-gray-500">
                    I confirm that this report is accurate and I'm willing to provide additional information if needed
                  </span>
                </label>
              </div>

              <div className="flex gap-3 mt-4">
                <Button
                  variant="outline"
                  onClick={() => setShowReportModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="danger"
                  onClick={handleReportSubmit}
                >
                  Submit Report
                </Button>
              </div>
            </div>
          )
        }
      />

      {/* Evidence Upload Tip */}
      <div className="mt-4 p-3 bg-primary/5 rounded-xl flex items-start gap-3">
        <Icon name="Info" size={18} className="text-primary mt-0.5" library="fi" />
        <div>
          <p className="text-xs font-medium text-primary">Evidence helps enforcement</p>
          <p className="text-xs text-gray-500 mt-1">
            Uploading a receipt or photo of the seller helps NAFDAC take faster action against counterfeiters.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ScanResultFake;