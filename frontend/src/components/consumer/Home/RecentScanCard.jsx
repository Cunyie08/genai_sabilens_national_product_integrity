// src/components/consumer/Home/RecentScanCard.jsx

import React from 'react';
import Card from '../../common/Card';
import Icon from '../../common/Icon';

const RecentScanCard = ({ product, status, time, verified, productImage }) => {
  const statusColors = {
    authentic: 'text-success',
    suspicious: 'text-warning',
    fake: 'text-danger'
  };

  const statusBgColors = {
    authentic: 'bg-success/10',
    suspicious: 'bg-warning/10',
    fake: 'bg-danger/10'
  };

  const getStatusIcon = () => {
    switch(status) {
      case 'authentic':
        return <Icon name="CheckCircle" size={14} className="text-success" library="fi" />;
      case 'suspicious':
        return <Icon name="AlertTriangle" size={14} className="text-warning" library="fi" />;
      case 'fake':
        return <Icon name="XCircle" size={14} className="text-danger" library="fi" />;
      default:
        return null;
    }
  };

  return (
    <Card className="flex items-center gap-3 mb-3 hover:shadow-card transition-shadow p-2">
      {/* Product Image - No fallback hardcoded images */}
      <div className="w-16 h-16 rounded-xl overflow-hidden bg-gray-100 flex-shrink-0">
        {productImage ? (
          <img 
            src={productImage} 
            alt={product}
            className="w-full h-full object-cover"
            onError={(e) => {
              e.target.onerror = null;
              e.target.style.display = 'none';
              e.target.parentElement.innerHTML = `
                <div class="w-full h-full flex items-center justify-center bg-gray-100">
                  <svg class="w-8 h-8 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
              `;
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gray-100">
            <Icon name="Image" size={24} className="text-gray-300" library="fi" />
          </div>
        )}
      </div>

      {/* Product Details */}
      <div className="flex-1 min-w-0">
        <h3 className="font-semibold text-gray-900 truncate">{product || 'Unknown Product'}</h3>
        <div className="flex items-center gap-2 mt-1">
          <span className={`text-xs px-2 py-0.5 rounded-full ${statusBgColors[status]} ${statusColors[status]} flex items-center gap-1`}>
            {getStatusIcon()}
            {status === 'authentic' ? 'Authentic' : status === 'suspicious' ? 'Suspicious' : 'Fake'}
          </span>
          {verified && (
            <span className="text-xs text-success flex items-center gap-1">
              <Icon name="Check" size={12} className="text-success" library="fi" />
              Verified
            </span>
          )}
        </div>
      </div>

      {/* Time */}
      <div className="text-right flex-shrink-0">
        <p className="text-xs text-gray-400">{time || 'Recently'}</p>
      </div>
    </Card>
  );
};

export default RecentScanCard;