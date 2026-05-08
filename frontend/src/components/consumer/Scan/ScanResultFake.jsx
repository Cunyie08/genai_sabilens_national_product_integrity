import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../../common/Icon';
import Card from '../../common/Card';
import Button from '../../common/Button';
import Modal from '../../common/Modal';

const ScanResultFake = ({ onBack, onReportToAuthority }) => {
  const navigate = useNavigate();
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportSubmitted, setReportSubmitted] = useState(false);
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
            : 95
        )
      );
      
      const confidenceLabel = aiResult?.confidence_label || 'Confidence Label';

      const warnings = aiResult?.warnings || [];
      const issues = warnings.length > 0
        ? warnings.map((w) => w?.message || w?.type || String(w))
        : aiResult?.detail
          ? [aiResult.detail]
          : ['Product did not match NAFDAC registry', 'Packaging anomalies detected'];

      const data = {
        id: scanId || `scan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        product: aiResult?.evidence_package?.product_name || 'Unregistered Product',
        productImage: productImage || null,
        category: aiResult?.evidence_package?.category || 'Unknown',
        manufacturer: 'Unknown / Unregistered',
        nafdacNumber: 'Not Found',
        batchNumber: 'Invalid',
        status: 'fake',
        similarity: displayConfidence,
        confidence: displayConfidence,
        confidenceLabel: confidenceLabel,
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
            // Extract city, state, country
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

  const handleScanAnother = () => {
    sessionStorage.removeItem('currentScan');
    navigate('/scan');
  };

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
            {scanData.productImage ? (
              <img 
                src={scanData.productImage} 
                alt={scanData.product}
                className="w-full h-full object-contain opacity-50"
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

        {/* 1. Risk Assessment */}
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

        {/* 2. Confidence Label (renamed from AI Confidence Score) */}
        <div className="p-4 border-b border-gray-100">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">{scanData.confidenceLabel}</span>
            <span className="text-sm font-bold text-danger">{scanData.confidence}%</span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full bg-danger rounded-full" style={{ width: `100%` }} />
          </div>
          <p className="text-xs text-gray-400 mt-2">
            {scanData.instruction || scanData.detail || 'High confidence — This product matches counterfeit patterns'}
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
            <Icon name="XCircle" size={18} className="text-danger" library="fi" />
            Why this product is flagged:
          </h3>
          <div className="bg-danger/5 rounded-xl p-4">
            <p className="text-sm text-gray-700">
              {scanData.instruction || 'This product has failed verification and shows signs of being counterfeit. Do not purchase it.'}
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
          variant="danger" 
          fullWidth
          onClick={() => setShowReportModal(true)}
          icon="Flag"
        >
          Report
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
          onClick={handleRescan}
          icon="RotateCcw"
        >
          Rescan Product
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