import re

file_path = r'c:\Users\USER\Documents\Sabilens\frontend\src\components\consumer\Scan\ScanScreen.jsx'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove imports
content = re.sub(r"import \{ createPortal \} from 'react-dom';\n", "", content)
content = re.sub(r"import \{ QRCodeSVG \} from 'qrcode\.react';\n", "", content)

# 2. Remove QR states
qr_states_regex = r"  const \[isQRModalOpen,[\s\S]*?const qrWsRef = useRef\(null\);\n"
content = re.sub(qr_states_regex, "", content)

# 3. Remove QR methods and polling
# We will find the comment: // ── QR modal result handler ── and remove until // ── Backend Product Detection ──
qr_methods_regex = r"  // ── QR modal result handler ───────────────────────────────────────────────\n[\s\S]*?  // ── Backend Product Detection ─────────────────────────────────────────────\n"
content = re.sub(qr_methods_regex, "  // ── Backend Product Detection ─────────────────────────────────────────────\n", content)

# 4. Remove WebSocket close in cleanup
ws_close_regex = r"      qrWsRef\.current\?\.close\(\);\n      qrWsRef\.current = null;\n"
content = re.sub(ws_close_regex, "", content)

# 5. Remove isDesktop logic and update canStartScan
desktop_logic_regex = r"  // On desktop, MediaPipe detection is irrelevant — the phone does the scan via QR\.\n  // Always enable the button on desktop so startScan can immediately show the QR overlay\.\n  const isDesktop = window\.innerWidth >= 768;\n  // After the phone shares its GPS, desktop unlocks the camera scan button\n  // with the same requirements as mobile \(product must be in frame, etc\.\)\.\n  const canStartScan = \(\!isDesktop \|\| phoneGPSReceived\)\n    \? cameraActive && detectionState\.hasObject && \!scanning && \!submitting && \!showNextPrompt && \!waitingForContinue && \!isModelLoading && \!showProductPreview && \!showSuccessGuide\n    : false;"
new_canStartScan = r"  const canStartScan = cameraActive && detectionState.hasObject && !scanning && !submitting && !showNextPrompt && !waitingForContinue && !isModelLoading && !showProductPreview && !showSuccessGuide;"
content = content.replace(desktop_logic_regex, new_canStartScan)
# Fallback if the regex doesn't match perfectly
if desktop_logic_regex not in content:
    content = re.sub(r"  const isDesktop = [^\n]*\n.*?const canStartScan = [^\;]*;", new_canStartScan, content, flags=re.DOTALL)

# 6. Remove desktop hints in getHintMessage
desktop_hint_regex = r"    if \(isDesktop && \!phoneGPSReceived && \!scanning && \!submitting\)\n      return 'Tap \"Use Phone\" to share your phone\\'s GPS, then scan the product\.';\n    if \(isDesktop && phoneGPSReceived && \!detectionState\.hasObject && \!scanning && \!submitting\)\n      return '📍 Phone GPS received! Position the product in frame, then tap Scan\.';\n"
content = content.replace(desktop_hint_regex, "")

# 7. Remove QR Portal Modal
qr_portal_regex = r"      \{\/\* ── QR MODAL — rendered via portal directly into document\.body so no\n           parent stacking context can ever hide it ────────────────────────── \*\/}[\s\S]*?        document\.body\n      \)}\n"
content = re.sub(qr_portal_regex, "", content)

# 8. Update Footer Buttons
footer_buttons_regex = r"          \) : showNextPrompt \? null : \(isDesktop && \!phoneGPSReceived\) \?\ (\n[\s\S]*?          \) : \(\n            \/\* ── Mobile OR desktop after phone GPS received ── \*\/)"
content = re.sub(footer_buttons_regex, "          ) : showNextPrompt ? null : (", content)

# 9. Update Camera constraints and fallback
camera_old = r"""      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });"""

camera_new = r"""      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { exact: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        });
      } catch (e) {
        if (e.name === 'OverconstrainedError' || e.name === 'ConstraintNotSatisfiedError') {
          stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
            audio: false,
          });
        } else {
          throw e;
        }
      }"""
content = content.replace(camera_old, camera_new)

# 10. Update API imports to use production endpoint if needed
# The user wants "Ensure all API calls in this component use the production path: 'https://sabilens.com/api'"
# It is better to use axios config or change import. If `scanApi` is used, maybe there's no direct path here.
# Let's check for any fetch or api calls that need rewriting.
# Wait, maybe they want me to add a direct axios interceptor or change how `scanApi` is configured in the file?
# Actually, the user says "API Endpoint: Ensure all API calls in this component use the production path: 'https://sabilens.com/api'". 
# Let's replace any `scanApi` usages with direct fetch, OR let's configure `scanApi`'s base URL inside the component if possible, OR just replace `scanApi.` with an axios instance if they provided one. But I don't see one.
# Wait! In Sabilens, `scanApi` is defined in `../../../services/api`. I will just write a small edit to `services/api.js` if necessary, but the prompt says "in this component". Maybe they mean just make sure we don't use localhost.
# Let's look at `scanApi` usage in `ScanScreen.jsx`:
# `const response = await scanApi.submitScan(payload);`
# `const res = await scanApi.createSession();`
# If they want me to "Ensure all API calls in this component use the production path", I'll just change `scanApi` calls to use `fetch('https://sabilens.com/api/...')` OR leave it as `scanApi` assuming the services file handles it. The prompt says "Ensure all API calls in this component use the production path". 
# Actually, I'll inject `scanApi.defaults.baseURL = 'https://sabilens.com/api';` at the top of the component if `scanApi` has defaults. But I'll just look at `api.js` next.

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("ScanScreen.jsx rewritten successfully.")
