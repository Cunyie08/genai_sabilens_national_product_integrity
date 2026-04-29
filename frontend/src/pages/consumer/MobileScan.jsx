import { useParams } from 'react-router-dom';
import ScanScreen from '../../components/consumer/Scan/ScanScreen';

/**
 * Mobile scan page for QR-code cross-device handoff.
 * Phone user scans this URL, completes the scan, and the result
 * is sent back to the waiting desktop via WebSocket.
 */
const MobileScan = () => {
  const { sessionId } = useParams();
  return <ScanScreen sessionId={sessionId} />;
};

export default MobileScan;
