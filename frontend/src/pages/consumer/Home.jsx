// src/pages/consumer/Home.jsx

import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import ConsumerBottomNav from '../../components/layout/ConsumerBottomNav';
import HomeScreen from '../../components/consumer/Home/HomeScreen';
import Modal from '../../components/common/Modal';
import Button from '../../components/common/Button';
import Icon from '../../components/common/Icon';
import { getRecentScans } from '../../services/scanHistory';

const Home = () => {
  const navigate = useNavigate();
  const [isFirstTimeUser, setIsFirstTimeUser] = useState(false);
  const [recentScans, setRecentScans] = useState([]);
  const [profileImage, setProfileImage] = useState(null);
  const [selectedScan, setSelectedScan] = useState(null);
  const hasLoadedRef = useRef(false);

  // Get current user from localStorage
  const currentUser = JSON.parse(localStorage.getItem('currentUser') || '{}');
  const firstName = currentUser.firstName || 'Guest';
  
  // Get full user data from users array
  const users = JSON.parse(localStorage.getItem('users') || '[]');
  const userData = users.find(u => u.phone === currentUser.phone) || {};
  
  // Get profile image from user data
  useEffect(() => {
    if (userData.profileImage) {
      setProfileImage(userData.profileImage);
    }
  }, [userData.profileImage]);
  
  // Generate initials from first and last name
  const getInitials = () => {
    const first = currentUser.firstName?.[0] || '';
    const last = currentUser.lastName?.[0] || '';
    return (first + last).toUpperCase() || 'U';
  };

  // Load recent scans in background
  const loadRecentScans = async () => {
    try {
      const scans = await getRecentScans(5);
      setRecentScans(scans);
    } catch (error) {
      console.error('Error loading scans:', error);
    }
  };

  // Initial load
  useEffect(() => {
    if (!hasLoadedRef.current) {
      hasLoadedRef.current = true;
      loadRecentScans();
    }
  }, []);

  // Check if this is first time user
  useEffect(() => {
    const hasScanned = localStorage.getItem('hasScanned') === 'true';
    const hasSeenWelcome = localStorage.getItem('hasSeenWelcome') === 'true';
    
    if (!hasSeenWelcome && !hasScanned) {
      setIsFirstTimeUser(true);
      localStorage.setItem('hasSeenWelcome', 'true');
    }
  }, []);

  const handleScanPress = () => {
    navigate('/scan');
  };

  const handleViewAll = () => {
    navigate('/scan-history');
  };

  const handleScanItemPress = (scan) => {
    // Show modal instead of navigating
    console.log('Scan clicked:', scan); // Debug log
    setSelectedScan(scan);
  };

  const handleProfilePress = () => {
    navigate('/profile');
  };

  const handleCloseModal = () => {
    setSelectedScan(null);
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
      
      // Close modal
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

  // Image fallback handler
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

  // Refresh scans when returning to home
  useEffect(() => {
    const handleFocus = () => {
      loadRecentScans();
      
      // Refresh profile image when returning to home
      const updatedUsers = JSON.parse(localStorage.getItem('users') || '[]');
      const updatedUserData = updatedUsers.find(u => u.phone === currentUser.phone) || {};
      if (updatedUserData.profileImage) {
        setProfileImage(updatedUserData.profileImage);
      }
    };
    
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [currentUser.phone]);

  return (
    <div className="min-h-screen bg-background pb-20">
      <HomeScreen
        firstName={firstName}
        userInitials={getInitials()}
        profileImage={profileImage}
        recentScans={recentScans}
        onScanPress={handleScanPress}
        onViewAllPress={handleViewAll}
        onScanItemPress={handleScanItemPress}
        onProfilePress={handleProfilePress}
        isFirstTimeUser={isFirstTimeUser}
      />
      <ConsumerBottomNav />

      {/* Scan Detail Modal */}
      <Modal
        isOpen={!!selectedScan}
        onClose={handleCloseModal}
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
    </div>
  );
};

export default Home;