// src/services/scanHistory.js

import { scanApi } from './api';

// Save a new scan to history (now uses backend API)
export const saveScan = async (scanData) => {
  try {
    // Check if user is logged in
    const currentUser = JSON.parse(localStorage.getItem('currentUser') || '{}');
    if (!currentUser.id && !currentUser.phone) {
      console.warn('No user logged in, cannot save scan to backend');
      return false;
    }
    
    // Prepare scan data for backend
    const payload = {
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
    };
    
    // Call backend API to save scan
    const response = await scanApi.saveScan(payload);
    
    if (response && response.data) {
      console.log('Scan saved to backend:', response.data);
      return true;
    }
    return false;
  } catch (error) {
    console.error('Error saving scan to backend:', error);
    return false;
  }
};

// Alias for backward compatibility - maintains old function name
export const saveScanToHistory = saveScan;

// Get all scans for current user (from backend)
export const getUserScanHistory = async () => {
  try {
    const currentUser = JSON.parse(localStorage.getItem('currentUser') || '{}');
    if (!currentUser.id && !currentUser.phone) {
      console.warn('No user logged in');
      return [];
    }
    
    const response = await scanApi.getScanHistory();
    const result = response.data || {};
    const scans = result.scans || result || [];
    
    // Transform backend data to frontend format
    return scans.map(scan => ({
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
  } catch (error) {
    console.error('Error loading scan history from backend:', error);
    return [];
  }
};

// Get recent scans (last N for home screen)
export const getRecentScans = async (limit = 5) => {
  const history = await getUserScanHistory();
  return history.slice(0, limit);
};

// Get scan by ID
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

// Delete a specific scan by ID
export const deleteScan = async (scanId) => {
  try {
    const response = await scanApi.deleteScan(scanId);
    return response && response.success !== false;
  } catch (error) {
    console.error('Error deleting scan:', error);
    return false;
  }
};

// Clear all scan history for current user
export const clearScanHistory = async () => {
  try {
    const response = await scanApi.clearScanHistory();
    return response && response.success !== false;
  } catch (error) {
    console.error('Error clearing scan history:', error);
    return false;
  }
};

// Get scan count by status (from backend)
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

// Get product image (fallback function - returns null to use placeholder icons)
export const getProductImage = (productName, category) => {
  // Return null to use placeholder icons instead of hardcoded images
  return null;
};

// Generate a unique scan ID (for frontend use only)
export const generateScanId = () => {
  return `scan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

// Default export for convenience
export default {
  saveScan,
  saveScanToHistory,
  getUserScanHistory,
  getRecentScans,
  getScanById,
  deleteScan,
  clearScanHistory,
  getScanStats,
  getProductImage,
  generateScanId
};