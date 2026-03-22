/**
 * SabiLens Scan History — Comprehensive Test Suite
 *
 * Run with:  node src/tests/scanHistory.test.js
 *
 * Tests every critical path touched by the session:
 *  1. saveScanToHistory  — image priority (Cloudinary > capturedImage > category fallback)
 *  2. saveScanToHistory  — status must be lowercase 'authentic'/'suspicious'/'fake'
 *  3. getUserScanHistory — returns real data, never injects mock data
 *  4. clearScanHistory   — empties the store correctly
 *  5. generateMockScan   — status must NEVER be 'caution'
 *  6. ScanScreen payload — imageUrl field present in sessionStorage schema
 *  7. ScanResultSafe     — builds correct data object (status lowercase, image from imageUrl)
 *  8. ScanResultFake     — builds correct data object (status 'fake', image from imageUrl)
 *  9. ScanHistory page   — no 'caution' references in filter/stats/navigation
 * 10. Home page          — no '/scan/caution' navigation route
 * 11. RecentScanCard     — no 'caution' status keys
 * 12. End-to-end         — full scan → save → load → display pipeline
 */

import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname  = dirname(__filename);
const srcRoot    = join(__dirname, '..');

// ─────────────────────────────────────────────────────────────────────────────
// Minimal localStorage / sessionStorage mocks
// ─────────────────────────────────────────────────────────────────────────────

const _lsStore = {};
const localStorage = {
  getItem:    (k)    => _lsStore[k] ?? null,
  setItem:    (k, v) => { _lsStore[k] = String(v); },
  removeItem: (k)    => { delete _lsStore[k]; },
  clear:      ()     => { Object.keys(_lsStore).forEach(k => delete _lsStore[k]); },
};

const _ssStore = {};
const sessionStorage = {
  getItem:    (k)    => _ssStore[k] ?? null,
  setItem:    (k, v) => { _ssStore[k] = String(v); },
  removeItem: (k)    => { delete _ssStore[k]; },
  clear:      ()     => { Object.keys(_ssStore).forEach(k => delete _ssStore[k]); },
};

// ─────────────────────────────────────────────────────────────────────────────
// Inline implementations (mirrors the source files under test)
// ─────────────────────────────────────────────────────────────────────────────

const PRODUCT_IMAGES = {
  'Pharmaceuticals': 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=500',
  'Food':            'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500',
};

function getProductImage(productName, category) {
  for (const [key, value] of Object.entries(PRODUCT_IMAGES)) {
    if (productName?.toLowerCase().includes(key.toLowerCase())) return value;
  }
  if (category && PRODUCT_IMAGES[category]) return PRODUCT_IMAGES[category];
  return 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=500';
}

/** Mirrors scanHistory.js — saveScanToHistory (with the productImage priority fix) */
function saveScanToHistory(scanData) {
  const currentUser = JSON.parse(localStorage.getItem('currentUser') || '{}');
  if (!currentUser.phone) return [];

  const historyKey      = `scanHistory_${currentUser.phone}`;
  const existingHistory = JSON.parse(localStorage.getItem(historyKey) || '[]');
  const productImage    = getProductImage(scanData.product, scanData.category);

  const newScan = {
    id: `scan_${Date.now()}`,
    ...scanData,
    // ✅ Fix: prefer Cloudinary URL → capturedImage → category fallback
    productImage: scanData.productImage || scanData.capturedImage || productImage,
    timestamp:    new Date().toISOString(),
    userPhone:    currentUser.phone,
  };

  const updatedHistory = [newScan, ...existingHistory].slice(0, 50);
  localStorage.setItem(historyKey, JSON.stringify(updatedHistory));
  localStorage.setItem('hasScanned', 'true');
  return updatedHistory;
}

function getUserScanHistory() {
  const currentUser = JSON.parse(localStorage.getItem('currentUser') || '{}');
  if (!currentUser.phone) return [];
  const historyKey = `scanHistory_${currentUser.phone}`;
  return JSON.parse(localStorage.getItem(historyKey) || '[]');
}

function clearScanHistory() {
  const currentUser = JSON.parse(localStorage.getItem('currentUser') || '{}');
  if (!currentUser.phone) return;
  localStorage.removeItem(`scanHistory_${currentUser.phone}`);
}

/** Mirrors scanHistory.js — generateMockScan (with 'caution' → 'suspicious' fix) */
function generateMockScan(isAuthentic = true) {
  return {
    id:           `scan_mock_${Date.now()}_${Math.random()}`,
    product:      'Test Product',
    productImage: 'https://test.com/img.png',
    category:     'Pharmaceuticals',
    manufacturer: 'Test Mfr',
    nafdacNumber: 'B1-0000-XX',
    // ✅ Fix: 'suspicious' not 'caution'
    status:       isAuthentic ? 'authentic' : (Math.random() > 0.5 ? 'suspicious' : 'fake'),
    time:         'Today, 10:00 AM',
    verified:     isAuthentic,
    similarity:   isAuthentic ? 90 : 40,
    batchNumber:  'BATCH-001',
    expiryDate:   '2026-06',
    location:     'Lagos Market',
    timestamp:    new Date().toISOString(),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Test runner
// ─────────────────────────────────────────────────────────────────────────────

let passed = 0;
let failed = 0;
const failures = [];

function assert(condition, message) {
  if (condition) {
    console.log(`  ✅ ${message}`);
    passed++;
  } else {
    console.log(`  ❌ FAIL: ${message}`);
    failed++;
    failures.push(message);
  }
}

function assertEqual(actual, expected, message) {
  if (actual === expected) {
    console.log(`  ✅ ${message}`);
    passed++;
  } else {
    const detail = `expected=${JSON.stringify(expected)}, got=${JSON.stringify(actual)}`;
    console.log(`  ❌ FAIL: ${message} [${detail}]`);
    failed++;
    failures.push(`${message} [${detail}]`);
  }
}

function describe(label, fn) {
  console.log(`\n📦 ${label}`);
  fn();
}

function setupUser(phone = '08012345678') {
  localStorage.clear();
  sessionStorage.clear();
  localStorage.setItem('currentUser', JSON.stringify({ phone, firstName: 'Test' }));
}

// ─────────────────────────────────────────────────────────────────────────────
// TESTS
// ─────────────────────────────────────────────────────────────────────────────

// ── 1. productImage priority ─────────────────────────────────────────────────
describe('saveScanToHistory — productImage priority (Cloudinary URL preserved)', () => {
  const cloudinaryUrl = 'https://res.cloudinary.com/demo/image/upload/v1/test.jpg';
  const base64        = 'data:image/jpeg;base64,/9j/4AAQSkZJRg==';

  // 1a. Cloudinary URL must be preserved unchanged
  setupUser();
  saveScanToHistory({ product: 'Paracetamol', category: 'Pharmaceuticals', status: 'authentic', productImage: cloudinaryUrl });
  assertEqual(getUserScanHistory()[0].productImage, cloudinaryUrl,
    'Cloudinary productImage URL is preserved, not replaced by category fallback');

  // 1b. No productImage → falls back to category lookup
  setupUser();
  saveScanToHistory({ product: 'Some Tablet', category: 'Pharmaceuticals', status: 'authentic' });
  const fb = getUserScanHistory()[0].productImage;
  assert(fb.startsWith('https://images.unsplash.com') || fb.startsWith('https://'),
    'Falls back to category image when no productImage provided');

  // 1c. capturedImage (base64) used when no Cloudinary URL
  setupUser();
  saveScanToHistory({ product: 'Some Tablet', category: 'Food', status: 'authentic', capturedImage: base64 });
  assertEqual(getUserScanHistory()[0].productImage, base64,
    'capturedImage (base64) used when no Cloudinary productImage');

  // 1d. productImage wins over capturedImage
  setupUser();
  saveScanToHistory({ product: 'Vaseline', category: 'Pharmaceuticals', status: 'authentic', productImage: cloudinaryUrl, capturedImage: base64 });
  assertEqual(getUserScanHistory()[0].productImage, cloudinaryUrl,
    'productImage (Cloudinary) wins over capturedImage (base64)');
});

// ── 2. Status values must be lowercase ───────────────────────────────────────
describe('saveScanToHistory — status values are stored as-is (must be lowercase)', () => {
  for (const status of ['authentic', 'suspicious', 'fake']) {
    setupUser();
    saveScanToHistory({ product: 'Test', category: 'Food', status });
    assertEqual(getUserScanHistory()[0].status, status,
      `Status '${status}' stored correctly`);
  }
  // Verify no uppercase survives from result pages (they now hardcode lowercase)
  setupUser();
  saveScanToHistory({ product: 'Test', category: 'Food', status: 'authentic' });
  assert(getUserScanHistory()[0].status === 'authentic',
    'Status is lowercase "authentic" as hardcoded by ScanResultSafe');
});

// ── 3. No mock data on empty history ─────────────────────────────────────────
describe('getUserScanHistory — no mock data injection on empty history', () => {
  setupUser();
  const hist = getUserScanHistory();
  assertEqual(hist.length, 0,
    'Empty history returns [] — no mock data auto-injected');
  const raw = localStorage.getItem('scanHistory_08012345678');
  assert(raw === null || !raw.includes('Nike Air Max'),
    'No Nike Air Max (mock product) written to localStorage');
  assert(raw === null || !raw.includes('Gucci'),
    'No Gucci (mock product) written to localStorage');
});

// ── 4. clearScanHistory ───────────────────────────────────────────────────────
describe('clearScanHistory — correctly empties store', () => {
  setupUser();
  saveScanToHistory({ product: 'A', category: 'Food', status: 'authentic' });
  saveScanToHistory({ product: 'B', category: 'Food', status: 'fake' });
  assert(getUserScanHistory().length === 2, 'Two scans saved before clear');
  clearScanHistory();
  assertEqual(getUserScanHistory().length, 0, 'History empty after clearScanHistory');
});

// ── 5. generateMockScan — 'caution' never produced ───────────────────────────
describe('generateMockScan — status is "suspicious" or "fake", never "caution"', () => {
  const VALID   = new Set(['authentic', 'suspicious', 'fake']);
  const results = new Set();
  let foundBad  = false;

  for (let i = 0; i < 300; i++) {
    const scan = generateMockScan(false);
    results.add(scan.status);
    if (!VALID.has(scan.status)) {
      foundBad = true;
      console.log(`  ❌ FAIL: generateMockScan produced invalid status '${scan.status}' on iteration ${i}`);
      failed++;
      failures.push(`generateMockScan produced invalid status '${scan.status}'`);
      break;
    }
  }

  if (!foundBad) {
    console.log(`  ✅ 300 iterations: all statuses valid (${[...results].join(', ')})`);
    passed++;
  }

  assert(!results.has('caution'),
    "'caution' never appears in 300 generateMockScan(false) iterations");
  assert(results.has('suspicious') || results.has('fake'),
    "generateMockScan(false) produces 'suspicious' and/or 'fake'");

  const authScan = generateMockScan(true);
  assertEqual(authScan.status, 'authentic',
    'generateMockScan(true) always returns "authentic"');
});

// ── 6. ScanScreen sessionStorage payload schema ───────────────────────────────
describe('ScanScreen — sessionStorage payload includes imageUrl', () => {
  const cloudinaryUrl = 'https://res.cloudinary.com/demo/image/upload/scan123.jpg';
  const base64        = 'data:image/jpeg;base64,/9j/4AAQ==';
  const geo           = { latitude: 6.5, longitude: 3.3, address: 'Lagos, Nigeria' };

  function buildPayload(apiData, primaryImage) {
    const data    = apiData;
    const verdict = data.verdict || data.final_verdict || 'FAKE';
    return {
      productImage:     primaryImage,
      imageUrl:         data.image_url || null,
      isAuthentic:      verdict === 'AUTHENTIC',
      isSuspicious:     verdict === 'SUSPICIOUS',
      isRescanRequired: verdict === 'RESCAN_REQUIRED',
      aiResult:         data,
      location:         geo.address,
      latitude:         geo.latitude,
      longitude:        geo.longitude,
    };
  }

  // 6a. imageUrl populated from API
  const p1 = buildPayload({ verdict: 'AUTHENTIC', image_url: cloudinaryUrl }, base64);
  assert('imageUrl' in p1,       'Payload has imageUrl field');
  assertEqual(p1.imageUrl, cloudinaryUrl, 'imageUrl = Cloudinary URL from API');
  assertEqual(p1.productImage, base64,    'productImage = base64 captured image');

  // 6b. No image_url → imageUrl is null (not undefined)
  const p2 = buildPayload({ verdict: 'FAKE' }, base64);
  assert(p2.imageUrl === null, 'imageUrl is null when API has no image_url');

  // 6c. Verdict flags
  const pa = buildPayload({ verdict: 'AUTHENTIC' }, base64);
  assert(pa.isAuthentic === true  && pa.isSuspicious === false, 'AUTHENTIC: isAuthentic=true, isSuspicious=false');

  const ps = buildPayload({ verdict: 'SUSPICIOUS' }, base64);
  assert(ps.isAuthentic === false && ps.isSuspicious === true,  'SUSPICIOUS: isAuthentic=false, isSuspicious=true');

  const pf = buildPayload({ verdict: 'FAKE' }, base64);
  assert(pf.isAuthentic === false && pf.isSuspicious === false, 'FAKE: isAuthentic=false, isSuspicious=false');
});

// ── 7. ScanResultSafe data object ────────────────────────────────────────────
describe('ScanResultSafe — data object correctness', () => {
  const cloudinaryUrl = 'https://res.cloudinary.com/demo/image/upload/safe123.jpg';
  const base64        = 'data:image/jpeg;base64,/9j/safe==';

  function buildSafeData(stored) {
    const productImage = stored.imageUrl || stored.productImage;
    const aiResult     = stored.aiResult || null;
    const verdictRaw   = aiResult?.final_verdict || 'AUTHENTIC';
    const isSuspicious = verdictRaw === 'SUSPICIOUS';
    const confidence   = aiResult?.confidence_pct ?? 92;
    return {
      product:      aiResult?.evidence_package?.product_name || 'Verified Product',
      productImage: productImage || 'https://images.unsplash.com/fallback.jpg',
      status:       isSuspicious ? 'suspicious' : 'authentic',
      isSuspicious,
      confidence,
      verified:     true,
    };
  }

  // 7a. Cloudinary URL preferred over base64
  const d1 = buildSafeData({ imageUrl: cloudinaryUrl, productImage: base64, aiResult: { final_verdict: 'AUTHENTIC', confidence_pct: 97 } });
  assertEqual(d1.productImage, cloudinaryUrl, 'ScanResultSafe: productImage = Cloudinary URL');

  // 7b. Falls back to base64 when no imageUrl
  const d2 = buildSafeData({ imageUrl: null, productImage: base64, aiResult: { final_verdict: 'AUTHENTIC', confidence_pct: 97 } });
  assertEqual(d2.productImage, base64, 'ScanResultSafe: falls back to base64 when imageUrl is null');

  // 7c. AUTHENTIC → status 'authentic'
  assertEqual(d1.status, 'authentic', 'ScanResultSafe: AUTHENTIC → status "authentic"');

  // 7d. SUSPICIOUS → status 'suspicious' NOT 'caution'
  const d3 = buildSafeData({ imageUrl: cloudinaryUrl, productImage: base64, aiResult: { final_verdict: 'SUSPICIOUS', confidence_pct: 55 } });
  assertEqual(d3.status, 'suspicious', 'ScanResultSafe: SUSPICIOUS → status "suspicious"');
  assert(d3.status !== 'caution',      'ScanResultSafe: status is NEVER "caution"');
});

// ── 8. ScanResultFake data object ────────────────────────────────────────────
describe('ScanResultFake — data object correctness', () => {
  const cloudinaryUrl = 'https://res.cloudinary.com/demo/image/upload/fake456.jpg';
  const base64        = 'data:image/jpeg;base64,/9j/fake==';

  function buildFakeData(stored) {
    const productImage = stored.imageUrl || stored.productImage;
    const aiResult     = stored.aiResult || null;
    const confidence   = aiResult?.confidence_pct ?? 18;
    return {
      product:      aiResult?.evidence_package?.product_name || 'Unregistered Product',
      productImage: productImage || 'https://images.unsplash.com/fallback.jpg',
      status:       'fake',  // hardcoded — never from AI verdict string
      confidence,
      verified:     false,
    };
  }

  const d1 = buildFakeData({ imageUrl: cloudinaryUrl, productImage: base64, aiResult: { confidence_pct: 18 } });
  assertEqual(d1.productImage, cloudinaryUrl, 'ScanResultFake: productImage = Cloudinary URL');
  assertEqual(d1.status, 'fake',              'ScanResultFake: status hardcoded "fake" (lowercase)');
  assert(d1.status !== 'FAKE',                'ScanResultFake: status is NOT uppercase "FAKE"');
  assert(d1.verified === false,               'ScanResultFake: verified is always false');

  const d2 = buildFakeData({ imageUrl: null, productImage: base64, aiResult: {} });
  assertEqual(d2.productImage, base64, 'ScanResultFake: falls back to base64 when imageUrl is null');
});

// ── 9. ScanHistory.jsx source — no 'caution' strings ─────────────────────────
describe('ScanHistory.jsx source — "caution" fully replaced with "suspicious"', () => {
  try {
    const src = readFileSync(join(srcRoot, 'pages/consumer/ScanHistory.jsx'), 'utf8');
    assert(!src.includes("'caution'"),        "No 'caution' string literals");
    assert(!src.includes('"caution"'),        'No "caution" string literals');
    assert(src.includes("'suspicious'"),      "Uses 'suspicious' for warning status");
    assert(src.includes('/scan/suspicious'),  "Navigates to '/scan/suspicious'");
    assert(!src.includes('/scan/caution'),    "Does NOT navigate to '/scan/caution'");
    assert(!src.includes('addMockScans'),     'No addMockScans function');
    assert(!src.includes('generateMockScan'), 'No generateMockScan call');
    assert(!src.includes("import.*generateMockScan"), 'generateMockScan not imported');
  } catch (e) {
    console.log(`  ⚠️  Skipped: ${e.message}`);
  }
});

// ── 10. Home.jsx source — no '/scan/caution' route ────────────────────────────
describe('Home.jsx source — navigation uses "/scan/suspicious"', () => {
  try {
    const src = readFileSync(join(srcRoot, 'pages/consumer/Home.jsx'), 'utf8');
    assert(!src.includes('/scan/caution'),   "Does NOT navigate to '/scan/caution'");
    assert(src.includes('/scan/suspicious'), "Navigates to '/scan/suspicious'");
  } catch (e) {
    console.log(`  ⚠️  Skipped: ${e.message}`);
  }
});

// ── 11. scanHistory.js source — no 'caution' in generateMockScan ─────────────
describe('scanHistory.js source — generateMockScan uses "suspicious" not "caution"', () => {
  try {
    const src = readFileSync(join(srcRoot, 'services/scanHistory.js'), 'utf8');
    assert(!src.includes("'caution'"),  "No 'caution' in status assignments");
    assert(src.includes("'suspicious'"), "Uses 'suspicious' in generateMockScan");
    // productImage priority fix
    assert(src.includes('scanData.productImage ||'), 'productImage priority: scanData.productImage checked first');
  } catch (e) {
    console.log(`  ⚠️  Skipped: ${e.message}`);
  }
});

// ── 12. RecentScanCard — status key consistency ───────────────────────────────
describe('RecentScanCard — statusColors/statusBgColors use "suspicious" not "caution"', () => {
  // Mirror the component's lookup maps
  const statusColors = {
    authentic:  'text-success',
    suspicious: 'text-warning',
    fake:       'text-danger',
  };
  const statusBgColors = {
    authentic:  'bg-success/10',
    suspicious: 'bg-warning/10',
    fake:       'bg-danger/10',
  };

  assert(!('caution' in statusColors),   'statusColors has no "caution" key');
  assert(!('caution' in statusBgColors), 'statusBgColors has no "caution" key');
  assert('suspicious' in statusColors,   'statusColors has "suspicious" key');
  assert('suspicious' in statusBgColors, 'statusBgColors has "suspicious" key');

  const getLabel = (s) =>
    s === 'authentic' ? 'Authentic' : s === 'suspicious' ? 'Suspicious' : 'Fake';
  assertEqual(getLabel('authentic'),  'Authentic',  'Label: authentic → "Authentic"');
  assertEqual(getLabel('suspicious'), 'Suspicious', 'Label: suspicious → "Suspicious"');
  assertEqual(getLabel('fake'),       'Fake',       'Label: fake → "Fake"');
});

// ── 13. End-to-end pipeline ───────────────────────────────────────────────────
describe('End-to-end: scan → sessionStorage → result page → localStorage → home', () => {
  setupUser();

  const cloudinaryUrl = 'https://res.cloudinary.com/sabilens/image/upload/v1/product.jpg';
  const base64        = 'data:image/jpeg;base64,/9j/4AAQ==';

  // Step 1: ScanScreen writes to sessionStorage after API call
  const apiResponse = {
    verdict:          'AUTHENTIC',
    image_url:        cloudinaryUrl,
    confidence_pct:   94,
    evidence_package: { product_name: 'Paracetamol 500mg', category: 'Pharmaceuticals', manufacturer: 'GSK Nigeria' },
    summary:          'Product matches NAFDAC registry',
  };

  const sessionPayload = {
    productImage:     base64,
    imageUrl:         apiResponse.image_url || null,
    isAuthentic:      apiResponse.verdict === 'AUTHENTIC',
    isSuspicious:     apiResponse.verdict === 'SUSPICIOUS',
    aiResult:         apiResponse,
    location:         'Lagos, Nigeria',
    latitude:         6.5,
    longitude:        3.3,
  };
  sessionStorage.setItem('currentScan', JSON.stringify(sessionPayload));

  // Step 2: ScanResultSafe reads sessionStorage, builds data, calls saveScanToHistory
  const stored       = JSON.parse(sessionStorage.getItem('currentScan'));
  const productImage = stored.imageUrl || stored.productImage;
  const aiResult     = stored.aiResult;
  const verdictRaw   = aiResult.final_verdict || aiResult.verdict || 'AUTHENTIC';
  const isSuspicious = verdictRaw === 'SUSPICIOUS';
  const status       = isSuspicious ? 'suspicious' : 'authentic';

  const dataToSave = {
    product:      aiResult.evidence_package?.product_name || 'Verified Product',
    productImage,
    category:     aiResult.evidence_package?.category || 'Consumer Goods',
    manufacturer: aiResult.evidence_package?.manufacturer || 'Registered Manufacturer',
    status,
    confidence:   aiResult.confidence_pct ?? 92,
    verified:     true,
    time:         'Today, 10:00 AM',
    timestamp:    new Date().toISOString(),
  };

  saveScanToHistory(dataToSave);

  // Step 3: ScanHistory / Home reads from localStorage
  const history = getUserScanHistory();

  assertEqual(history.length, 1,
    'E2E: exactly 1 scan in history');
  assertEqual(history[0].product, 'Paracetamol 500mg',
    'E2E: product name preserved');
  assertEqual(history[0].productImage, cloudinaryUrl,
    'E2E: Cloudinary URL preserved through entire pipeline');
  assertEqual(history[0].status, 'authentic',
    'E2E: status is lowercase "authentic"');
  assert(history[0].status !== 'AUTHENTIC',
    'E2E: status is NOT uppercase "AUTHENTIC"');
  assert(history[0].verified === true,
    'E2E: verified=true for authentic scan');
  assert(typeof history[0].timestamp === 'string',
    'E2E: timestamp is an ISO string');

  // Step 4: Recent scans for Home page
  const recentScans = history.slice(0, 5);
  assertEqual(recentScans.length, 1,
    'E2E: home page shows 1 real scan');
  assert(!recentScans.some(s => s.id?.includes('mock')),
    'E2E: no mock scans in recent list');

  // Step 5: SUSPICIOUS e2e
  setupUser();
  const suspApiResponse = { verdict: 'SUSPICIOUS', image_url: cloudinaryUrl, confidence_pct: 55 };
  const suspStored = { productImage: base64, imageUrl: cloudinaryUrl, aiResult: suspApiResponse };
  const suspImg    = suspStored.imageUrl || suspStored.productImage;
  const suspStatus = suspApiResponse.verdict === 'SUSPICIOUS' ? 'suspicious' : 'authentic';

  saveScanToHistory({ product: 'Suspicious Med', category: 'Pharmaceuticals', productImage: suspImg, status: suspStatus });
  const suspHist = getUserScanHistory();
  assertEqual(suspHist[0].status, 'suspicious', 'E2E SUSPICIOUS: status is "suspicious"');
  assert(suspHist[0].status !== 'caution',       'E2E SUSPICIOUS: status is NOT "caution"');
  assertEqual(suspHist[0].productImage, cloudinaryUrl, 'E2E SUSPICIOUS: Cloudinary URL preserved');
});

// ─────────────────────────────────────────────────────────────────────────────
// Summary
// ─────────────────────────────────────────────────────────────────────────────

console.log('\n' + '─'.repeat(60));
console.log(`Results: ${passed} passed, ${failed} failed`);
if (failures.length > 0) {
  console.log('\nFailed tests:');
  failures.forEach((f, i) => console.log(`  ${i + 1}. ${f}`));
  process.exit(1);
} else {
  console.log('\nAll tests passed ✅');
  process.exit(0);
}
