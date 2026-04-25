// src/components/consumer/Scan/ScanResultRescan.jsx

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../../common/Icon';
import Card from '../../common/Card';
import Button from '../../common/Button';

const ScanResultRescan = ({ onBack, onScanAnother }) => {
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

      const data = {
        id: scanId || `scan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        product: aiResult?.evidence_package?.product_name || 'Unknown Product',
        productImage: productImage || null,
        category: aiResult?.evidence_package?.category || 'Unknown',
        manufacturer: aiResult?.evidence_package?.manufacturer || 'Unknown',
        instruction: aiResult?.simple_instruction || 'This product could not be found in our database.',
        summary: aiResult?.summary || 'Product not registered in our system',
        detail: aiResult?.detail || 'The scanned product does not match any records in our verified database.',
        location: scanLocation || (scanLat && scanLng ? `${scanLat.toFixed(4)}° N, ${scanLng.toFixed(4)}° E` : 'Location unavailable'),
        latitude: scanLat,
        longitude: scanLng,
        time: 'Today, ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
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

  const handleScanAnother = () => {
    sessionStorage.removeItem('currentScan');
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

  const handleContactSupport = () => {
    window.location.href = 'mailto:support@sabilens.com?subject=Product%20Not%20Found%20in%20Database';
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
            <Icon name="Database" size={40} className="text-warning" library="fi" />
          </div>
          <h1 className="text-2xl font-bold text-warning mb-2">Product Not in Database</h1>
          <p className="text-gray-600 text-sm">
            This product could not be found in our verified product database.
          </p>
        </div>

        {/* Product Image */}
        <div className="p-4 border-b border-gray-100">
          <div className="bg-gray-100 rounded-xl h-48 flex items-center justify-center overflow-hidden relative">
            {scanData.productImage ? (
              <img 
                src={scanData.productImage} 
                alt={scanData.product}
                className="w-full h-full object-contain opacity-60"
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
              NOT FOUND
            </div>
          </div>
        </div>

        {/* Explanation Section */}
        <div className="p-5 border-b border-gray-100">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 bg-warning/10 rounded-full flex items-center justify-center">
              <Icon name="Info" size={16} className="text-warning" library="fi" />
            </div>
            <h3 className="font-semibold text-gray-900">Why is this happening?</h3>
          </div>
          <div className="bg-warning/5 rounded-xl p-4">
            <p className="text-sm text-gray-700 mb-3">
              {scanData.instruction || "This product is not currently registered in our verified product database."}
            </p>
            <ul className="space-y-2 text-sm">
              <li className="flex items-start gap-3">
                <div className="w-5 h-5 bg-warning/10 rounded-full flex items-center justify-center mt-0.5 shrink-0">
                  <Icon name="AlertCircle" size={12} className="text-warning" library="fi" />
                </div>
                <span className="text-gray-600">The product may be new and not yet registered</span>
              </li>
              <li className="flex items-start gap-3">
                <div className="w-5 h-5 bg-warning/10 rounded-full flex items-center justify-center mt-0.5 shrink-0">
                  <Icon name="AlertCircle" size={12} className="text-warning" library="fi" />
                </div>
                <span className="text-gray-600">The NAFDAC number could be invalid or not in our system</span>
              </li>
              <li className="flex items-start gap-3">
                <div className="w-5 h-5 bg-warning/10 rounded-full flex items-center justify-center mt-0.5 shrink-0">
                  <Icon name="AlertCircle" size={12} className="text-warning" library="fi" />
                </div>
                <span className="text-gray-600">The image quality may be insufficient for proper identification</span>
              </li>
            </ul>
          </div>
        </div>

        {/* What You Can Do */}
        <div className="p-5 border-b border-gray-100">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center">
              <Icon name="Lightbulb" size={16} className="text-primary" library="fi" />
            </div>
            <h3 className="font-semibold text-gray-900">What you can do</h3>
          </div>
          <div className="space-y-3">
            <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-xl">
              <div className="w-6 h-6 bg-primary/10 rounded-full flex items-center justify-center shrink-0">
                <Icon name="Camera" size={12} className="text-primary" library="fi" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-800">Try rescanning</p>
                <p className="text-xs text-gray-500">Ensure good lighting and clear label visibility</p>
              </div>
            </div>
            <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-xl">
              <div className="w-6 h-6 bg-primary/10 rounded-full flex items-center justify-center shrink-0">
                <Icon name="Shield" size={12} className="text-primary" library="fi" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-800">Check the NAFDAC number</p>
                <p className="text-xs text-gray-500">Verify the NAFDAC number format (e.g., A4-1234567)</p>
              </div>
            </div>
            <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-xl">
              <div className="w-6 h-6 bg-primary/10 rounded-full flex items-center justify-center shrink-0">
                <Icon name="Mail" size={12} className="text-primary" library="fi" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-800">Contact support</p>
                <p className="text-xs text-gray-500">Report missing products to help us improve our database</p>
              </div>
            </div>
          </div>
        </div>

        {/* Location Captured */}
        <div className="p-5">
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
          onClick={handleContactSupport}
          icon="Mail"
        >
          Contact Support
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

      {/* Info Tip */}
      <div className="mt-6 p-4 bg-primary/5 rounded-xl flex items-start gap-3 border border-primary/10">
        <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center shrink-0">
          <Icon name="Info" size={16} className="text-primary" library="fi" />
        </div>
        <div>
          <p className="text-xs font-medium text-primary">Missing product?</p>
          <p className="text-xs text-gray-500 mt-1">
            If you believe this product is legitimate, please contact support to help us add it to our database.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ScanResultRescan;