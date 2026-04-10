// src/pages/consumer/ScanHistory.jsx

import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../../components/common/Icon';
import Card from '../../components/common/Card';
import Button from '../../components/common/Button';
import ConsumerBottomNav from '../../components/layout/ConsumerBottomNav';
import { getUserScanHistory, clearScanHistory, getScanStats } from '../../services/scanHistory';
import Modal from '../../components/common/Modal';

const ScanHistory = () => {
  const navigate = useNavigate();
  const [scans, setScans] = useState([]);
  const [stats, setStats] = useState({ total: 0, authentic: 0, suspicious: 0, fake: 0 });
  const [filter, setFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedScan, setSelectedScan] = useState(null);
  const [showClearModal, setShowClearModal] = useState(false);
  const [showFilterModal, setShowFilterModal] = useState(false);
  const [sortOrder, setSortOrder] = useState('newest');
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [isClearing, setIsClearing] = useState(false);
  const [showSkeleton, setShowSkeleton] = useState(true);
  const hasLoadedRef = useRef(false);
  const scansCacheRef = useRef([]);
  const statsCacheRef = useRef({ total: 0, authentic: 0, suspicious: 0, fake: 0 });

  // Load scans from cache first, then refresh
  const loadScans = async (showCache = true) => {
    try {
      if (showCache && scansCacheRef.current.length > 0) {
        setScans(scansCacheRef.current);
        setStats(statsCacheRef.current);
        setShowSkeleton(false);
      }
      
      const freshHistory = await getUserScanHistory();
      const uniqueFreshScans = [];
      const seenFreshIds = new Set();
      for (const scan of freshHistory) {
        if (!seenFreshIds.has(scan.id)) {
          seenFreshIds.add(scan.id);
          uniqueFreshScans.push(scan);
        }
      }
      
      scansCacheRef.current = uniqueFreshScans;
      setScans(uniqueFreshScans);
      
      const freshStats = await getScanStats();
      statsCacheRef.current = freshStats;
      setStats(freshStats);
      setShowSkeleton(false);
      
    } catch (error) {
      console.error('Error loading scans:', error);
      setShowSkeleton(false);
    } finally {
      setIsInitialLoad(false);
    }
  };

  useEffect(() => {
    if (!hasLoadedRef.current) {
      hasLoadedRef.current = true;
      loadScans(true);
    }
  }, []);

  useEffect(() => {
    const handleFocus = () => {
      loadScans(false);
    };
    
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, []);

  const getFilteredScans = () => {
    let filtered = [...scans];
    
    if (filter !== 'all') {
      filtered = filtered.filter(scan => scan.status === filter);
    }
    
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(scan => 
        (scan.product?.toLowerCase() || '').includes(term) ||
        (scan.manufacturer?.toLowerCase() || '').includes(term) ||
        (scan.category?.toLowerCase() || '').includes(term)
      );
    }
    
    filtered.sort((a, b) => {
      const dateA = a.timestamp || new Date(a.date || 0).getTime();
      const dateB = b.timestamp || new Date(b.date || 0).getTime();
      return sortOrder === 'newest' ? dateB - dateA : dateA - dateB;
    });
    
    return filtered;
  };

  const handleScanClick = (scan) => {
    console.log('Scan clicked:', scan); // Debug log
    setSelectedScan(scan);
  };

  const handleViewDetails = () => {
    if (selectedScan) {
      // Get status - ensure it's lowercase
      let statusLower = (selectedScan.status || '').toLowerCase();
      
      // Debug log
      console.log('Selected scan status:', selectedScan.status, 'Normalized:', statusLower);
      
      // Fallback - if status is empty, try to determine from other fields
      if (!statusLower || statusLower === '') {
        if (selectedScan.verified === true) {
          statusLower = 'authentic';
        } else if (selectedScan.similarity && selectedScan.similarity < 30) {
          statusLower = 'fake';
        } else {
          statusLower = 'suspicious';
        }
      }
      
      const statusUpper = statusLower === 'authentic' ? 'AUTHENTIC' : statusLower === 'fake' ? 'FAKE' : 'SUSPICIOUS';
      const confidenceValue = selectedScan.similarity || (statusLower === 'authentic' ? 92 : statusLower === 'fake' ? 95 : 55);
      
      sessionStorage.setItem('currentScan', JSON.stringify({
        productImage: selectedScan.productImage,
        imageUrl: selectedScan.productImage,
        product_name: selectedScan.product,
        aiResult: {
          final_verdict: statusUpper,
          confidence_score: confidenceValue / 100,
          display_confidence: confidenceValue,
          confidence_label: statusLower === 'authentic' ? 'Authenticity Confidence' : statusLower === 'fake' ? 'Counterfeit Confidence' : 'Suspicion Confidence',
          simple_instruction: selectedScan.instruction || (
            statusLower === 'authentic' 
              ? 'This product appears authentic. Safe to purchase.'
              : statusLower === 'fake'
              ? 'Do not buy this product. It appears to be counterfeit.'
              : 'This product shows some irregularities. Please verify before use.'
          ),
          evidence_package: {
            product_name: selectedScan.product,
            category: selectedScan.category,
            manufacturer: selectedScan.manufacturer,
            nafdac_number: selectedScan.nafdacNumber,
            batch_number: selectedScan.batchNumber,
            expiry_date: selectedScan.expiryDate
          },
          warnings: selectedScan.warnings || [],
          signals_used: selectedScan.signalsUsed || [],
          summary: selectedScan.summary || '',
          detail: selectedScan.detail || '',
          severity: selectedScan.severity || (statusLower === 'fake' ? 'CRITICAL' : statusLower === 'suspicious' ? 'MEDIUM' : 'LOW'),
          action: selectedScan.action || (statusLower === 'fake' ? 'DO NOT BUY' : statusLower === 'suspicious' ? 'VERIFY BEFORE USE' : 'BUY')
        },
        fromHistory: true,
        scan_id: selectedScan.id,
        location: selectedScan.location,
        latitude: selectedScan.latitude,
        longitude: selectedScan.longitude
      }));
      
      // Close modal first, then navigate
      setSelectedScan(null);
      
      // Navigate based on status
      console.log('Navigating to:', statusLower);
      if (statusLower === 'authentic') {
        navigate('/scan/safe');
      } else if (statusLower === 'fake') {
        navigate('/scan/fake');
      } else if (statusLower === 'suspicious') {
        navigate('/scan/suspicious');
      } else {
        navigate('/scan/suspicious'); // Default to suspicious
      }
    }
  };

  const handleClearHistory = async () => {
    setIsClearing(true);
    try {
      await clearScanHistory();
      scansCacheRef.current = [];
      statsCacheRef.current = { total: 0, authentic: 0, suspicious: 0, fake: 0 };
      await loadScans(false);
      setShowClearModal(false);
    } catch (error) {
      console.error('Error clearing history:', error);
    } finally {
      setIsClearing(false);
    }
  };

  const getStatusBadge = (status) => {
    const statusLower = (status || '').toLowerCase();
    switch(statusLower) {
      case 'authentic':
        return <span className="px-2 py-0.5 bg-success/10 text-success text-xs rounded-full font-medium">Authentic</span>;
      case 'suspicious':
        return <span className="px-2 py-0.5 bg-warning/10 text-warning text-xs rounded-full font-medium">Suspicious</span>;
      case 'fake':
        return <span className="px-2 py-0.5 bg-danger/10 text-danger text-xs rounded-full font-medium">Fake</span>;
      default:
        return null;
    }
  };

  const getStatusIcon = (status) => {
    const statusLower = (status || '').toLowerCase();
    switch(statusLower) {
      case 'authentic':
        return <Icon name="CheckCircle" size={20} className="text-success" library="fi" />;
      case 'suspicious':
        return <Icon name="AlertTriangle" size={20} className="text-warning" library="fi" />;
      case 'fake':
        return <Icon name="XCircle" size={20} className="text-danger" library="fi" />;
      default:
        return <Icon name="HelpCircle" size={20} className="text-gray-400" library="fi" />;
    }
  };

  const filteredScans = getFilteredScans();

  const handleImageError = (e) => {
    e.target.style.display = 'none';
    const parent = e.target.parentElement;
    if (parent) {
      parent.innerHTML = `
        <div class="w-full h-full flex items-center justify-center bg-gray-100">
          <svg class="w-8 h-8 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
      `;
    }
  };

  const SkeletonCard = () => (
    <Card className="p-3 animate-pulse">
      <div className="flex gap-3">
        <div className="w-16 h-16 rounded-xl bg-gray-200" />
        <div className="flex-1">
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
          <div className="h-3 bg-gray-200 rounded w-1/2 mb-2" />
          <div className="h-2 bg-gray-200 rounded w-1/3" />
        </div>
      </div>
    </Card>
  );

  return (
    <div className="min-h-screen bg-background pb-20">
      {/* Header */}
      <div className="bg-white px-4 pt-12 pb-3 sticky top-0 z-10 shadow-soft">
        <div className="flex items-center gap-3 mb-3">
          <button 
            onClick={() => navigate('/home')}
            className="w-9 h-9 rounded-full flex items-center justify-center bg-gray-50 hover:bg-gray-100 transition-colors"
          >
            <Icon name="ArrowLeft" size={18} className="text-gray-600" library="fi" />
          </button>
          <h1 className="text-xl font-bold text-gray-900">Scan History</h1>
        </div>

        {/* Search Bar */}
        <div className="relative">
          <Icon name="Search" size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" library="fi" />
          <input
            type="text"
            placeholder="Search products, brands..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary bg-gray-50"
          />
        </div>
      </div>

      {/* Stats Summary */}
      <div className="px-4 py-3">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <Card className="p-2 text-center">
            <p className="text-lg font-bold text-primary">{stats.total}</p>
            <p className="text-[10px] text-gray-400">Total</p>
          </Card>
          <Card className="p-2 text-center">
            <p className="text-lg font-bold text-success">{stats.authentic}</p>
            <p className="text-[10px] text-gray-400">Safe</p>
          </Card>
          <Card className="p-2 text-center">
            <p className="text-lg font-bold text-warning">{stats.suspicious}</p>
            <p className="text-[10px] text-gray-400">Suspicious</p>
          </Card>
          <Card className="p-2 text-center">
            <p className="text-lg font-bold text-danger">{stats.fake}</p>
            <p className="text-[10px] text-gray-400">Fake</p>
          </Card>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="sticky top-[116px] z-10 bg-background px-4 py-2 border-b border-gray-100">
        <div className="flex items-center justify-between gap-2">
          <div className="flex-1 overflow-x-auto scrollbar-hide -mx-1 px-1">
            <div className="flex gap-1.5 min-w-max">
              <button
                onClick={() => setFilter('all')}
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
                  filter === 'all' 
                    ? 'bg-primary text-white shadow-sm' 
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                All ({stats.total})
              </button>
              <button
                onClick={() => setFilter('authentic')}
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
                  filter === 'authentic' 
                    ? 'bg-success text-white shadow-sm' 
                    : 'bg-success/10 text-success hover:bg-success/20'
                }`}
              >
                Authentic ({stats.authentic})
              </button>
              <button
                onClick={() => setFilter('suspicious')}
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
                  filter === 'suspicious'
                    ? 'bg-warning text-white shadow-sm'
                    : 'bg-warning/10 text-warning hover:bg-warning/20'
                }`}
              >
                Suspicious ({stats.suspicious})
              </button>
              <button
                onClick={() => setFilter('fake')}
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
                  filter === 'fake' 
                    ? 'bg-danger text-white shadow-sm' 
                    : 'bg-danger/10 text-danger hover:bg-danger/20'
                }`}
              >
                Fake ({stats.fake})
              </button>
            </div>
          </div>
          
          <button
            onClick={() => setShowFilterModal(true)}
            className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all ${
              filter !== 'all' || sortOrder !== 'newest' 
                ? 'bg-primary text-white' 
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <Icon name="Sliders" size={14} library="fi" />
          </button>
        </div>
      </div>

      {/* Scans List */}
      <div className="px-4 py-3">
        {showSkeleton && isInitialLoad ? (
          <div className="space-y-2.5">
            {[1, 2, 3, 4, 5].map((i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : filteredScans.length > 0 ? (
          <div className="space-y-2.5">
            {filteredScans.map((scan) => (
              <Card 
                key={scan.id} 
                className="cursor-pointer hover:shadow-card transition-all active:scale-[0.98] p-3"
                onClick={() => handleScanClick(scan)}
              >
                <div className="flex gap-3">
                  <div className="w-16 h-16 rounded-xl overflow-hidden bg-gray-100 flex-shrink-0">
                    {scan.productImage ? (
                      <img 
                        src={scan.productImage} 
                        alt={scan.product}
                        className="w-full h-full object-cover"
                        onError={handleImageError}
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-gray-100">
                        <Icon name="Image" size={24} className="text-gray-300" library="fi" />
                      </div>
                    )}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <h3 className="font-semibold text-gray-900 text-sm truncate flex-1">{scan.product || 'Unknown Product'}</h3>
                      {getStatusBadge(scan.status)}
                    </div>
                    
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1 text-xs">
                      {scan.category && (
                        <div className="flex items-center gap-1">
                          <Icon name="Tag" size={10} className="text-gray-400" library="fi" />
                          <span className="text-gray-500 truncate max-w-[100px]">{scan.category}</span>
                        </div>
                      )}
                      <div className="flex items-center gap-1">
                        <Icon name="Clock" size={10} className="text-gray-400" library="fi" />
                        <span className="text-gray-500 text-xs">{scan.time || 'Recently'}</span>
                      </div>
                    </div>
                    
                    {scan.status !== 'authentic' && scan.similarity && (
                      <div className="mt-2">
                        <div className="flex justify-between text-xs mb-0.5">
                          <span className="text-gray-400">Similarity</span>
                          <span className={scan.status === 'fake' ? 'text-danger text-[10px]' : 'text-warning text-[10px]'}>
                            {scan.similarity}%
                          </span>
                        </div>
                        <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
                          <div 
                            className={`h-full rounded-full ${scan.status === 'fake' ? 'bg-danger' : 'bg-warning'}`}
                            style={{ width: `${scan.similarity}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        ) : !isInitialLoad ? (
          <Card className="text-center py-12">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <Icon name="Clock" size={28} className="text-gray-400" library="fi" />
            </div>
            <h3 className="text-base font-semibold text-gray-900 mb-1">No scans yet</h3>
            <p className="text-xs text-gray-400 mb-4">Start scanning products to build your history</p>
            <div className="flex justify-center">
              <Button 
                variant="primary" 
                onClick={() => navigate('/scan')}
                icon="Camera"
                size="sm"
              >
                Scan Your First Product
              </Button>
            </div>
          </Card>
        ) : null}
      </div>

      {/* Clear History Button */}
      {scans.length > 0 && (
        <div className="px-4 py-3">
          <button
            onClick={() => setShowClearModal(true)}
            className="w-full py-2.5 text-danger text-sm border border-danger/20 rounded-xl hover:bg-danger/5 transition-colors flex items-center justify-center gap-2"
          >
            <Icon name="Trash2" size={16} library="fi" />
            Clear History
          </button>
        </div>
      )}

      {/* Scan Detail Modal */}
      <Modal
        isOpen={!!selectedScan}
        onClose={() => setSelectedScan(null)}
        type="custom"
        title={
          <div className="flex items-center gap-2">
            {selectedScan && getStatusIcon(selectedScan.status)}
            <span className="text-base">Scan Details</span>
          </div>
        }
        message={
          selectedScan && (
            <div className="space-y-3">
              <div className="text-center">
                <div className="w-24 h-24 mx-auto mb-2 rounded-xl overflow-hidden border border-gray-200 bg-gray-100">
                  {selectedScan.productImage ? (
                    <img 
                      src={selectedScan.productImage} 
                      alt={selectedScan.product}
                      className="w-full h-full object-cover"
                      onError={handleImageError}
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Icon name="Image" size={32} className="text-gray-300" library="fi" />
                    </div>
                  )}
                </div>
                <h3 className="text-lg font-bold text-gray-900 mb-1">{selectedScan.product || 'Unknown Product'}</h3>
                {getStatusBadge(selectedScan.status)}
              </div>
              
              <div className="bg-gray-50 rounded-xl p-3 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-gray-500">Date & Time</span>
                  <span className="text-xs font-medium">{selectedScan.time || 'Recently'}</span>
                </div>
                {selectedScan.category && (
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Category</span>
                    <span className="text-xs font-medium">{selectedScan.category}</span>
                  </div>
                )}
                {selectedScan.manufacturer && (
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Manufacturer</span>
                    <span className="text-xs font-medium">{selectedScan.manufacturer}</span>
                  </div>
                )}
                {selectedScan.nafdacNumber && (
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">NAFDAC Number</span>
                    <span className="text-xs font-mono font-medium">{selectedScan.nafdacNumber}</span>
                  </div>
                )}
                {selectedScan.batchNumber && (
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Batch Number</span>
                    <span className="text-xs font-mono font-medium">{selectedScan.batchNumber}</span>
                  </div>
                )}
                {selectedScan.expiryDate && (
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Expiry Date</span>
                    <span className="text-xs font-medium">{selectedScan.expiryDate}</span>
                  </div>
                )}
                {selectedScan.location && (
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Location</span>
                    <span className="text-xs font-medium truncate max-w-[200px]">{selectedScan.location}</span>
                  </div>
                )}
              </div>

              <Button
                variant="primary"
                fullWidth
                onClick={handleViewDetails}
                size="sm"
              >
                View Full Report
              </Button>
            </div>
          )
        }
      />

      {/* Clear History Confirmation Modal */}
      {showClearModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl overflow-hidden">
            <button
              onClick={() => setShowClearModal(false)}
              disabled={isClearing}
              className="absolute top-4 right-4 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center hover:bg-gray-200 transition-colors z-10 disabled:opacity-50"
            >
              <Icon name="X" size={16} className="text-gray-500" library="fi" />
            </button>

            <div className="p-6 pt-8">
              <div className="text-center mb-6">
                <div className="w-16 h-16 bg-warning/10 rounded-full flex items-center justify-center mx-auto mb-4">
                  {isClearing ? (
                    <div className="w-6 h-6 border-2 border-warning border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <Icon name="Trash2" size={28} className="text-warning" library="fi" />
                  )}
                </div>
                <h2 className="text-xl font-bold text-gray-900 mb-2">Clear History</h2>
                <p className="text-gray-600 text-sm">
                  {isClearing 
                    ? 'Deleting your scan history...' 
                    : 'Are you sure you want to clear all scan history? This action cannot be undone.'}
                </p>
              </div>

              <div className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={() => setShowClearModal(false)}
                  fullWidth
                  size="sm"
                  disabled={isClearing}
                >
                  Cancel
                </Button>
                <Button
                  variant="danger"
                  onClick={handleClearHistory}
                  fullWidth
                  size="sm"
                  disabled={isClearing}
                >
                  {isClearing ? 'Deleting...' : 'Clear All'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filter Options Modal */}
      <Modal
        isOpen={showFilterModal}
        onClose={() => setShowFilterModal(false)}
        type="info"
        title="Sort Options"
        message={
          <div className="space-y-3">
            <div>
              <p className="text-xs font-medium text-gray-700 mb-2">Sort by</p>
              <div className="space-y-1.5">
                <label className="flex items-center gap-2 p-2 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
                  <input
                    type="radio"
                    name="sort"
                    checked={sortOrder === 'newest'}
                    onChange={() => setSortOrder('newest')}
                    className="w-3.5 h-3.5 text-primary"
                  />
                  <span className="text-xs">Newest first</span>
                </label>
                <label className="flex items-center gap-2 p-2 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
                  <input
                    type="radio"
                    name="sort"
                    checked={sortOrder === 'oldest'}
                    onChange={() => setSortOrder('oldest')}
                    className="w-3.5 h-3.5 text-primary"
                  />
                  <span className="text-xs">Oldest first</span>
                </label>
              </div>
            </div>
          </div>
        }
      />

      <ConsumerBottomNav />
    </div>
  );
};

export default ScanHistory;