import { test, expect } from '@playwright/test';

/**
 * Diagnostic test to verify that the dynamic root_path refactoring
 * resolves the Nginx trailing slash mismatch.
 * 
 * Modified to bypass DB-dependent routes like /auth/login so the test 
 * passes regardless of Cloud SQL proxy state.
 */
test.describe('Backend Routing & Path-Agnostic Validation', () => {

  // Nginx Proxy Endpoint (simulated by Vite dev server locally, or real Nginx in prod)
  const PROXY_BASE_URL = 'http://localhost:3000';
  
  // Raw Uvicorn Socket Endpoint (bypassing Nginx)
  // Since Nginx strips the /api/ prefix using proxy_pass http://.../;
  // the raw socket natively listens to the stripped paths.
  const RAW_SOCKET_URL = 'http://127.0.0.1:8000';

  test('1. Proxy Route Check: /api/health', async ({ request }) => {
    // 1. Test hitting the endpoint through the standard Nginx/Proxy path
    const response = await request.get(`${PROXY_BASE_URL}/api/health`);

    expect(response.status()).toBe(200);
    const body = await response.json();
    console.log('Test 1 Body:', body);
    expect(body.status).toBe('healthy');
    
    console.log('[SUCCESS] Proxy Health Route is active');
  });

  test('2. Raw Socket Route Check: /health', async ({ request }) => {
    // 2. Test hitting the raw Uvicorn socket directly.
    // Because main.py uses root_path="/api" and stripped prefixes, 
    // the raw socket expects /health.
    const response = await request.get(`${RAW_SOCKET_URL}/health`);

    expect(response.status()).toBe(200);
    const body = await response.json();
    console.log('Test 2 Body:', body);
    expect(body.status).toBe('healthy');

    console.log('[SUCCESS] Raw Socket Health Route is active');
  });

  test('3. Proxy Deep Route Check: /api/consumer/scan/detect-product', async ({ request }) => {
    // 3. Test a deep endpoint through the proxy
    // We send a tiny 1x1 transparent PNG base64 to avoid image processing errors
    const dummyImageBase64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=";

    const response = await request.post(`${PROXY_BASE_URL}/api/consumer/scan/detect-product`, {
      data: {
        image_data: dummyImageBase64,
        phase: "front"
      },
      headers: {
        'Content-Type': 'application/json'
      }
    });

    // We expect 200 OK. Even if it says "no product detected", the route works.
    expect(response.status()).toBe(200);
    const body = await response.json();
    console.log('Test 3 Body:', body);
    expect(body.has_product).toBeDefined();
    console.log('[SUCCESS] Proxy Deep Route is active');
  });

  test('4. Raw Socket Deep Route Check: /consumer/scan/detect-product', async ({ request }) => {
    // 4. Test the deep endpoint directly on the raw socket
    const dummyImageBase64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=";

    const response = await request.post(`${RAW_SOCKET_URL}/consumer/scan/detect-product`, {
      data: {
        image_data: dummyImageBase64,
        phase: "front"
      },
      headers: {
        'Content-Type': 'application/json'
      }
    });

    expect(response.status()).toBe(200);
    const body = await response.json();
    console.log('Test 4 Body:', body);
    expect(body.has_product).toBeDefined();
    console.log('[SUCCESS] Raw Socket Deep Route is active');
  });

});
