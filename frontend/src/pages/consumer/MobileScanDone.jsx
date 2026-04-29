const MobileScanDone = () => (
  <div className="min-h-screen flex flex-col items-center justify-center p-8 text-center bg-gray-50">
    <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mb-6">
      <span className="text-green-600 text-5xl leading-none">✓</span>
    </div>
    <h1 className="text-2xl font-bold text-gray-900 mb-3">Scan complete!</h1>
    <p className="text-gray-500 max-w-xs leading-relaxed">
      Your scan result has been sent to the desktop. You can close this page.
    </p>
  </div>
);

export default MobileScanDone;
