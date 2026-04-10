// src/services/scanHistory.js

import { scanApi } from './api';

// Cache configuration
let scansCache = null;
let scansCacheTime = null;
const CACHE_DURATION = 30000; // 30 seconds - adjust as needed

// Track if refresh is needed (set by new scans)
let refreshNeeded = false;

// Cache for recent scans (separate from full history)
let recentScansCache = null;
let recentScansCacheTime = null;

// Save a new scan to history
export const saveScan = async (scanData) => {
  try {
    const currentUser = JSON.parse(localStorage.getItem('currentUser') || '{}');
    if (!currentUser.id && !currentUser.phone) {
      console.warn('No user logged in, cannot save scan to backend');
      return false;
    }
    
    const scanId = scanData.id || generateScanId();
    
    // Prepare scan data for backend
    const payload = {
      id: scanId,
      product_name: scanData.product,
      product_image_url: scanData.productImage,
      status: scanData.status,
      category: scanData.category,
      manufacturer: scanData.manufacturer,
      nafdac_number: scanData.nafdacNumber,
      batch_number: scanData.batchNumber,
      expiry_date: scanData.expiryDate,
      location_text: scanData.location,
      latitude: scanData.latitude,
      longitude: scanData.longitude,
      confidence_score: scanData.similarity ? scanData.similarity / 100 : scanData.confidence_score,
      scan_data: scanData.details || scanData.aiResult || {},
      timestamp: scanData.timestamp || Date.now()
    };
    
    const response = await scanApi.saveScan(payload);
    
    if (response && response.data) {
      // Mark that refresh is needed for all caches
      refreshNeeded = true;
      // Clear caches to force refresh on next load
      clearScansCache();
      clearRecentScansCache();
      
      console.log('Scan saved to backend:', response.data);
      return true;
    }
    return false;
  } catch (error) {
    console.error('Error saving scan to backend:', error);
    return false;
  }
};

// Alias for saveScan (for backward compatibility)
export const saveScanToHistory = saveScan;

// Clear scans cache
export const clearScansCache = () => {
  scansCache = null;
  scansCacheTime = null;
};

// Clear recent scans cache
export const clearRecentScansCache = () => {
  recentScansCache = null;
  recentScansCacheTime = null;
};

// Force refresh on next load
export const markRefreshNeeded = () => {
  refreshNeeded = true;
};

// Get all scans for current user (with caching)
export const getUserScanHistory = async (forceRefresh = false) => {
  try {
    const currentUser = JSON.parse(localStorage.getItem('currentUser') || '{}');
    if (!currentUser.id && !currentUser.phone) {
      console.warn('No user logged in');
      return [];
    }
    
    const shouldRefresh = forceRefresh || refreshNeeded;
    const isCacheValid = scansCache && scansCacheTime && (Date.now() - scansCacheTime) < CACHE_DURATION;
    
    // Return cached data if valid and no refresh needed
    if (!shouldRefresh && isCacheValid) {
      console.log('Returning cached scan history');
      return scansCache;
    }
    
    console.log('Fetching fresh scan history from backend');
    const response = await scanApi.getScanHistory();
    const result = response.data || {};
    const scans = result.scans || result || [];
    
    // Transform backend data to frontend format
    const transformed = scans.map(scan => ({
      id: scan.id,
      product: scan.product_name || 'Unknown Product',
      productImage: scan.product_image_url,
      status: scan.status?.toLowerCase() || 'suspicious',
      time: scan.created_at ? new Date(scan.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Recently',
      date: scan.created_at,
      timestamp: new Date(scan.created_at).getTime(),
      category: scan.category,
      manufacturer: scan.manufacturer,
      nafdacNumber: scan.nafdac_number,
      batchNumber: scan.batch_number,
      expiryDate: scan.expiry_date,
      location: scan.location_text,
      latitude: scan.latitude,
      longitude: scan.longitude,
      similarity: scan.confidence_score ? Math.round(scan.confidence_score * 100) : null,
      verified: scan.status === 'AUTHENTIC',
      details: scan.scan_data,
      confidence_score: scan.confidence_score
    }));
    
    // Update cache
    scansCache = transformed;
    scansCacheTime = Date.now();
    refreshNeeded = false; // Reset refresh flag
    
    return transformed;
  } catch (error) {
    console.error('Error loading scan history from backend:', error);
    return scansCache || [];
  }
};

// Get recent scans (with separate cache)
export const getRecentScans = async (limit = 5, forceRefresh = false) => {
  try {
    const currentUser = JSON.parse(localStorage.getItem('currentUser') || '{}');
    if (!currentUser.id && !currentUser.phone) {
      return [];
    }
    
    const shouldRefresh = forceRefresh || refreshNeeded;
    const isCacheValid = recentScansCache && recentScansCacheTime && (Date.now() - recentScansCacheTime) < CACHE_DURATION;
    
    // Return cached data if valid and no refresh needed
    if (!shouldRefresh && isCacheValid) {
      console.log('Returning cached recent scans');
      return recentScansCache.slice(0, limit);
    }
    
    // Fetch full history and cache recent scans
    const fullHistory = await getUserScanHistory(forceRefresh);
    recentScansCache = fullHistory;
    recentScansCacheTime = Date.now();
    
    return fullHistory.slice(0, limit);
  } catch (error) {
    console.error('Error loading recent scans:', error);
    return [];
  }
};

// Get scan by ID (no caching needed for single scan)
export const getScanById = async (scanId) => {
  try {
    const response = await scanApi.getScanById(scanId);
    if (response && response.data) {
      const scan = response.data;
      return {
        id: scan.id,
        product: scan.product_name || 'Unknown Product',
        productImage: scan.product_image_url,
        status: scan.status?.toLowerCase() || 'suspicious',
        time: scan.created_at ? new Date(scan.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Recently',
        date: scan.created_at,
        timestamp: new Date(scan.created_at).getTime(),
        category: scan.category,
        manufacturer: scan.manufacturer,
        nafdacNumber: scan.nafdac_number,
        batchNumber: scan.batch_number,
        expiryDate: scan.expiry_date,
        location: scan.location_text,
        similarity: scan.confidence_score ? Math.round(scan.confidence_score * 100) : null,
        verified: scan.status === 'AUTHENTIC',
        details: scan.scan_data
      };
    }
    return null;
  } catch (error) {
    console.error('Error getting scan by ID:', error);
    return null;
  }
};

// Delete a specific scan by ID (invalidate cache)
export const deleteScan = async (scanId) => {
  try {
    const response = await scanApi.deleteScan(scanId);
    if (response && response.success !== false) {
      // Invalidate caches
      refreshNeeded = true;
      clearScansCache();
      clearRecentScansCache();
      return true;
    }
    return false;
  } catch (error) {
    console.error('Error deleting scan:', error);
    return false;
  }
};

// Clear all scan history (invalidate cache)
export const clearScanHistory = async () => {
  try {
    const response = await scanApi.clearScanHistory();
    if (response && response.success !== false) {
      // Invalidate caches
      refreshNeeded = true;
      clearScansCache();
      clearRecentScansCache();
      return true;
    }
    return false;
  } catch (error) {
    console.error('Error clearing scan history:', error);
    return false;
  }
};

// Get scan count by status (from cache or fresh)
export const getScanStats = async () => {
  try {
    const history = await getUserScanHistory();
    return {
      total: history.length,
      authentic: history.filter(s => s.status === 'authentic').length,
      suspicious: history.filter(s => s.status === 'suspicious').length,
      fake: history.filter(s => s.status === 'fake').length
    };
  } catch (error) {
    console.error('Error getting scan stats:', error);
    return { total: 0, authentic: 0, suspicious: 0, fake: 0 };
  }
};

// Get product image (fallback function)
export const getProductImage = (productName, category) => {
  return null;
};

// Generate a unique scan ID
export const generateScanId = () => {
  return `scan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

// Force refresh on window focus (optional - for when user returns to app)
export const setupAutoRefresh = () => {
  const handleFocus = () => {
    refreshNeeded = true;
  };
  window.addEventListener('focus', handleFocus);
  return () => window.removeEventListener('focus', handleFocus);
};

// Default export
export default {
  saveScan,
  saveScanToHistory: saveScan,
  getUserScanHistory,
  getRecentScans,
  getScanById,
  deleteScan,
  clearScanHistory,
  getScanStats,
  getProductImage,
  generateScanId,
  clearScansCache,
  clearRecentScansCache,
  markRefreshNeeded,
  setupAutoRefresh
};