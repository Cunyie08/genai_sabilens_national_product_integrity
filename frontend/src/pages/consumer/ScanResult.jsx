import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import ConsumerBottomNav from '../../components/layout/ConsumerBottomNav';
import ScanResultSafe from '../../components/consumer/Scan/ScanResultSafe';
import ScanResultFake from '../../components/consumer/Scan/ScanResultFake';

const ScanResultRescan = ({ onRescan, onBack }) => {
  const storedScan = sessionStorage.getItem('currentScan');
  let aiResult = null;
  try { aiResult = storedScan ? JSON.parse(storedScan).aiResult : null; } catch {}

  return (
    <div className="px-6 py-8">
      <button onClick={onBack} className="mb-6">
        <span className="text-gray-500 text-sm">← Back</span>
      </button>
      <div className="text-center mb-8">
        <div className="w-20 h-20 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <span className="text-4xl">🔄</span>
        </div>
        <h1 className="text-2xl font-bold text-yellow-700 mb-2">RESCAN REQUIRED</h1>
        <p className="text-gray-600 text-sm">
          {aiResult?.simple_instruction || 'The AI could not make a confident determination. Please rescan the product with clearer images.'}
        </p>
      </div>
      <button
        onClick={onRescan}
        className="w-full bg-primary text-white py-4 rounded-xl font-semibold text-base"
      >
        Scan Again
      </button>
    </div>
  );
};

const ScanResult = () => {
  const navigate = useNavigate();
  const { result } = useParams();

  const handleBack = () => navigate('/home');
  const handleReportIssue = () => navigate('/report');
  const handleScanAnother = () => navigate('/scan');
  const handleReportToAuthority = () => navigate('/report');
  const handleRescan = () => navigate('/scan');

  let content;
  if (result === 'safe') {
    content = (
      <ScanResultSafe
        onBack={handleBack}
        onReportIssue={handleReportIssue}
        onScanAnother={handleScanAnother}
      />
    );
  } else if (result === 'rescan') {
    content = <ScanResultRescan onRescan={handleRescan} onBack={handleBack} />;
  } else {
    content = (
      <ScanResultFake
        onBack={handleBack}
        onReportToAuthority={handleReportToAuthority}
      />
    );
  }

  return (
    <div className="min-h-screen bg-background pb-20">
      {content}
      <ConsumerBottomNav />
    </div>
  );
};

export default ScanResult;