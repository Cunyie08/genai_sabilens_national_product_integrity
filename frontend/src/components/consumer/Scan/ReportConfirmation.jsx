import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../../common/Icon';
import Card from '../../common/Card';
import Button from '../../common/Button';

const ReportConfirmation = () => {
  const navigate = useNavigate();
  const [purchaseChannel, setPurchaseChannel] = useState('');
  const [locationLabel, setLocationLabel] = useState('Locating…');

  useEffect(() => {
    const scan = JSON.parse(sessionStorage.getItem('currentScan') || '{}');
    const lat = scan.latitude;
    const lng = scan.longitude;
    if (lat && lng) {
      fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=10&addressdetails=1`)
        .then((r) => r.json())
        .then((data) => {
          const a = data.address || {};
          const parts = [a.city || a.town || a.village || a.county, a.state].filter(Boolean);
          setLocationLabel(parts.length ? parts.join(', ') : data.display_name || 'Location captured');
        })
        .catch(() => setLocationLabel(`${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E`));
    } else {
      setLocationLabel('Location unavailable');
    }
  }, []);

  const channels = [
    'Market stall',
    'Roadside vendor',
    'Supermarket',
    'Supplier'
  ];

  const handleSubmit = () => {
    // Submit report logic
    navigate('/home');
  };

  return (
    <div className="px-6 py-8">
      <button
        onClick={() => navigate(-1)}
        className="mb-6"
      >
        <Icon name="ArrowLeft" size={24} className="text-gray-500" />
      </button>

      <Card className="mb-6">
        <div className="text-center mb-6">
          <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <Icon name="CheckCircle" size={32} className="text-success" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">GPS Locked</h2>
          <p className="text-sm text-gray-500">
            Location captured: {locationLabel}
          </p>
        </div>

        <div className="border-t border-gray-100 pt-6">
          <h3 className="font-semibold mb-4">Purchase Channel</h3>
          <div className="space-y-3">
            {channels.map((channel) => (
              <label
                key={channel}
                className={`flex items-center justify-between p-4 border rounded-xl cursor-pointer transition-colors ${
                  purchaseChannel === channel
                    ? 'border-primary bg-primary/5'
                    : 'border-gray-200 hover:bg-gray-50'
                }`}
              >
                <span className="font-medium">{channel}</span>
                <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                  purchaseChannel === channel
                    ? 'border-primary'
                    : 'border-gray-300'
                }`}>
                  {purchaseChannel === channel && (
                    <div className="w-3 h-3 bg-primary rounded-full" />
                  )}
                </div>
                <input
                  type="radio"
                  name="channel"
                  value={channel}
                  checked={purchaseChannel === channel}
                  onChange={(e) => setPurchaseChannel(e.target.value)}
                  className="hidden"
                />
              </label>
            ))}
          </div>
        </div>
      </Card>

      <Button
        variant="primary"
        fullWidth
        onClick={handleSubmit}
        disabled={!purchaseChannel}
      >
        Submit Report
      </Button>
    </div>
  );
};

export default ReportConfirmation;