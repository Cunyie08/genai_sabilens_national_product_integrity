// src/pages/consumer/Profile.jsx

import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import ConsumerBottomNav from '../../components/layout/ConsumerBottomNav';
import ProfileScreen from '../../components/consumer/Profile/ProfileScreen';
import Modal from '../../components/common/Modal';
import Button from '../../components/common/Button';
import { authApi } from '../../services/api';
import Icon from '../../components/common/Icon';

const Profile = () => {
  const navigate = useNavigate();
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const [userData, setUserData] = useState({});
  const [error, setError] = useState(null);
  const hasLoadedRef = useRef(false);
  const isMountedRef = useRef(true);

  // Get current user from localStorage (immediate fallback)
  const currentUser = JSON.parse(localStorage.getItem('currentUser') || '{}');

  // Fetch full user profile from backend in background
  useEffect(() => {
    isMountedRef.current = true;
    
    const fetchUserProfile = async () => {
      try {
        // If we already have cached data, show it immediately
        // Then update in background
        if (currentUser.id || currentUser.phone) {
          // Set initial data from localStorage immediately
          setUserData({
            id: currentUser.id,
            phone: currentUser.phone,
            firstName: currentUser.firstName,
            lastName: currentUser.lastName,
            email: currentUser.email,
            role: currentUser.role,
            state: currentUser.state,
            city: currentUser.city,
            preferredLanguage: currentUser.preferredLanguage || 'English',
            profileImage: currentUser.profileImage || currentUser.profile_image_url,
            createdAt: currentUser.createdAt,
          });
        }
        
        // Fetch fresh data in background
        const response = await authApi.getProfile();
        const profileData = response.data;
        
        if (isMountedRef.current) {
          const freshUserData = {
            id: profileData.id,
            phone: profileData.phone,
            firstName: profileData.first_name,
            lastName: profileData.last_name,
            email: profileData.email,
            role: profileData.role,
            state: profileData.state,
            city: profileData.city,
            preferredLanguage: profileData.preferred_language || 'English',
            profileImage: profileData.profile_image_url,
            createdAt: profileData.created_at,
            updatedAt: profileData.updated_at,
            lastLogin: profileData.last_login,
            status: profileData.status,
          };
          
          setUserData(freshUserData);
          
          // Update localStorage with fresh data
          const updatedUserData = {
            id: profileData.id,
            phone: profileData.phone,
            firstName: profileData.first_name,
            lastName: profileData.last_name,
            role: profileData.role,
            state: profileData.state,
            city: profileData.city,
            email: profileData.email,
            createdAt: profileData.created_at,
          };
          localStorage.setItem('currentUser', JSON.stringify(updatedUserData));
        }
      } catch (err) {
        console.error('Failed to fetch profile:', err);
        if (isMountedRef.current) {
          setError(err.message || 'Failed to load profile data');
          // Already have userData from localStorage, so no need to show error screen
        }
      }
    };

    // Only fetch if we have a user ID or phone
    if (currentUser.id || currentUser.phone) {
      fetchUserProfile();
    }
    
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Get scan history for stats (from localStorage - fast)
  const historyKey = `scanHistory_${userData.phone || currentUser.phone}`;
  const scans = JSON.parse(localStorage.getItem(historyKey) || '[]');
  
  // Calculate real stats from actual scan data
  const stats = {
    reports: scans.length,
    verified: scans.filter(s => s.status === 'authentic' || s.verdict === 'authentic' || s.verdict === 'AUTHENTIC').length,
    pending: scans.filter(s => s.status === 'caution' || s.status === 'pending' || s.verdict === 'caution' || s.verdict === 'SUSPICIOUS').length,
    fake: scans.filter(s => s.status === 'fake' || s.verdict === 'fake' || s.verdict === 'FAKE').length
  };

  // Get member since date from user creation
  const getMemberSince = () => {
    if (userData.createdAt) {
      const date = new Date(userData.createdAt);
      return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long',
        day: 'numeric'
      });
    }
    return 'January 2026';
  };

  // Calculate account age in days
  const getAccountAge = () => {
    if (userData.createdAt) {
      const created = new Date(userData.createdAt);
      const now = new Date();
      const diffTime = Math.abs(now - created);
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      return diffDays;
    }
    return 30;
  };

  // Get last active date
  const getLastActive = () => {
    if (scans.length > 0) {
      const lastScan = new Date(scans[0].timestamp);
      return lastScan.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric',
        year: 'numeric'
      });
    }
    if (userData.lastLogin) {
      const lastLogin = new Date(userData.lastLogin);
      return lastLogin.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric',
        year: 'numeric'
      });
    }
    return 'Never';
  };

  // Calculate scan frequency
  const getScanFrequency = () => {
    const days = getAccountAge();
    if (days > 0 && stats.reports > 0) {
      const avg = (stats.reports / days).toFixed(1);
      return `${avg} per day`;
    }
    return 'No scans yet';
  };

  // Get location display
  const getLocationDisplay = () => {
    if (userData.city && userData.state) {
      return `${userData.city}, ${userData.state}`;
    } else if (userData.state) {
      return userData.state;
    } else if (userData.city) {
      return userData.city;
    }
    return 'Not set';
  };

  const menuItems = [
    { 
      icon: 'Phone', 
      label: 'Phone Number', 
      value: userData.phone ? `+234 ${userData.phone}` : 'Not set' 
    },
    { 
      icon: 'MapPin', 
      label: 'Location', 
      value: getLocationDisplay()
    },
    { 
      icon: 'Mail', 
      label: 'Email', 
      value: userData.email || 'Not set' 
    },
    { 
      icon: 'Globe', 
      label: 'Language', 
      value: userData.preferredLanguage || 'English' 
    },
    { 
      icon: 'Star', 
      label: 'Reputation Score', 
      value: stats.verified > 0 ? '98%' : 'New User' 
    },
    { 
      icon: 'CheckCircle', 
      label: 'Verified Reports', 
      value: stats.verified.toString() 
    },
    { 
      icon: 'AlertTriangle', 
      label: 'Fake Detected', 
      value: stats.fake.toString() 
    },
  ];

  // Add dynamic activity summary items
  const activityItems = [
    {
      icon: 'Calendar',
      label: 'Member Since',
      value: getMemberSince()
    },
    {
      icon: 'Clock',
      label: 'Last Active',
      value: getLastActive()
    },
    {
      icon: 'Activity',
      label: 'Scan Frequency',
      value: getScanFrequency()
    },
    {
      icon: 'Award',
      label: 'Total Scans',
      value: stats.reports.toString()
    }
  ];

  const handleSettingClick = (setting) => {
    switch(setting) {
      case 'privacy':
        navigate('/privacy-policy');
        break;
      case 'terms':
        navigate('/terms-of-service');
        break;
      case 'help':
        navigate('/help-support');
        break;
      default:
        break;
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('currentUser');
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    setShowLogoutModal(false);
    navigate('/login');
  };

  const handleEditProfile = () => {
    navigate('/edit-profile', { state: { userData } });
  };

  // Show error state only if there's an error AND no user data
  // This prevents showing error screen if we have cached data
  if (error && !userData.phone && !userData.firstName) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center pb-20">
        <div className="text-center max-w-sm mx-auto px-6">
          <div className="w-16 h-16 bg-danger/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-accent mb-2">Unable to Load Profile</h3>
          <p className="text-gray-500 mb-4">{error}</p>
          <Button
            variant="primary"
            onClick={() => window.location.reload()}
          >
            Try Again
          </Button>
        </div>
      </div>
    );
  }

  // Always show profile screen immediately with whatever data we have
  // No loading screen - data loads in background
  return (
    <div className="min-h-screen bg-background pb-20">
      <ProfileScreen
        userData={userData}
        stats={stats}
        menuItems={menuItems}
        activityItems={activityItems}
        onSettingClick={handleSettingClick}
        onLogout={() => setShowLogoutModal(true)}
        onEditProfile={handleEditProfile}
      />
      <ConsumerBottomNav />

      {/* Logout Confirmation Modal - Custom modal without close button, with cancel icon */}
      {showLogoutModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl overflow-hidden">
            <button
              onClick={() => setShowLogoutModal(false)}
              className="absolute top-4 right-4 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center hover:bg-gray-200 transition-colors z-10"
            >
              <Icon name="X" size={16} className="text-gray-500" library="fi" />
            </button>

            <div className="p-6 pt-8">
              <div className="text-center mb-6">
                <div className="w-16 h-16 bg-warning/10 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Icon name="LogOut" size={28} className="text-warning" library="fi" />
                </div>
                <h2 className="text-xl font-bold text-gray-900 mb-2">Confirm Logout</h2>
                <p className="text-gray-600">
                  Are you sure you want to log out of your account?
                </p>
              </div>

              <div className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={() => setShowLogoutModal(false)}
                  fullWidth
                >
                  Cancel
                </Button>
                <Button
                  variant="danger"
                  onClick={handleLogout}
                  fullWidth
                >
                  Yes, Logout
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Profile;