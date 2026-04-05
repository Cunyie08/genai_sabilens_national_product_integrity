import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LayoutGrid, Users, Clock, Package, Map, Shield, Settings, HelpCircle,
  Search, Bell, LogOut, ChevronDown, Filter, X, Menu,
  TrendingUp, TrendingDown, AlertTriangle, FileText, Download, Eye
} from 'lucide-react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Title, Tooltip, Legend, Filler
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

// ─── DATA ────────────────────────────────────────────────────────────────────
const USERS_DATA = [
  { name: 'Chidi Okoro', initials: 'CO', color: '#7C3AED', phone: '+234 803 123 4567', score: 98, scans: 1402, lastActive: '2 MINS AGO', tier: 'TIER 1 CURATOR', rep: 98, earned: '₦42.5k', activity: [{ icon: '✅', text: 'Verified Batch #9921', loc: 'Yaba, Lagos', time: '4 mins ago' }, { icon: '💊', text: 'Scan: Panadol Extra', loc: 'Surulere, Lagos', time: '22 mins ago' }] },
  { name: 'Fatima Eze', initials: 'FE', color: '#059669', phone: '+234 812 987 6543', score: 82, scans: 856, lastActive: '15 MINS AGO', tier: 'TIER 2 CURATOR', rep: 82, earned: '₦18.2k', activity: [{ icon: '🍺', text: 'Scan: Heineken 330ml', loc: 'Kano, Sabon Gari', time: '15 mins ago' }] },
  { name: 'Benson Musa', initials: 'BM', color: '#D97706', phone: '+234 706 444 1122', score: 14, scans: 12, lastActive: '1 HOUR AGO', tier: 'TIER 3 CURATOR', rep: 14, earned: '₦0.8k', activity: [{ icon: '❌', text: 'Failed Verification', loc: 'Abuja, Garki', time: '1 hr ago' }] },
  { name: 'Adeola Bakare', initials: 'AB', color: '#2563EB', phone: '+234 801 555 9900', score: 91, scans: 2104, lastActive: '5 MINS AGO', tier: 'COMPLIANCE LEAD', rep: 91, earned: '₦68.1k', activity: [{ icon: '✅', text: 'Audit Completed #7741', loc: 'Lagos, VI', time: '5 mins ago' }] },
  { name: 'Ngozi Okafor', initials: 'NO', color: '#DC2626', phone: '+234 815 222 3344', score: 67, scans: 445, lastActive: '3 HOURS AGO', tier: 'TIER 2 CURATOR', rep: 67, earned: '₦11.4k', activity: [{ icon: '💊', text: 'Scan: Amoxicillin Syrup', loc: 'Enugu, Trans-Ekulu', time: '3 hrs ago' }] },
];
const SCANS_DATA = [
  { product: 'Paracetamol 500mg', nafdac: '04-2195', location: 'Lagos, Ikeja', user: '#772182', status: 'VALID', time: '2 mins ago', icon: '💊' },
  { product: 'Heineken 330ml Premium', nafdac: 'INVALID', location: 'Kano, Sabon Gari', user: '#881290', status: 'FAKE', time: '5 mins ago', icon: '🍺' },
  { product: 'Eva Water 75cl', nafdac: 'A1-0428', location: 'Abuja, Garki', user: '#334421', status: 'AUTHENTIC', time: '8 mins ago', icon: '💧' },
  { product: 'Samsung S23 Ultra', nafdac: 'N/A', location: 'Abuja, Wuse', user: '#122934', status: 'VALID', time: '12 mins ago', icon: '📱' },
  { product: 'Guinness Stout 600ml', nafdac: 'B1-0601', location: 'Port Harcourt, D/Line', user: '#994421', status: 'VALID', time: '18 mins ago', icon: '🍺' },
  { product: 'Amoxicillin Syrup', nafdac: 'INVALID', location: 'Kano, Sabon Gari', user: '#SL-1182', status: 'FAKE', time: '25 mins ago', icon: '💊' },
  { product: 'Peak Milk 400g', nafdac: 'C2-1100', location: 'Enugu, Trans-Ekulu', user: '#443312', status: 'AUTHENTIC', time: '31 mins ago', icon: '🥛' },
  { product: 'Malar-X 500mg', nafdac: 'INVALID', location: 'Kano Market', user: '#SL-9902', status: 'FAKE', time: '40 mins ago', icon: '💊' },
  { product: 'Dettol 250ml', nafdac: 'D3-4421', location: 'Lagos, Surulere', user: '#221089', status: 'VALID', time: '55 mins ago', icon: '🧴' },
  { product: 'Indomie Noodles 70g', nafdac: 'E1-2234', location: 'Oyo, Ibadan', user: '#556123', status: 'AUTHENTIC', time: '1 hr ago', icon: '🍜' },
];
const PRODUCTS_DATA = [
  { cat: 'Pharmaceuticals', name: 'Paracetamol 500mg', company: 'Emzor Pharma', nafdac: '04-2195', scans: 12443, fakes: 89, integrity: 99 },
  { cat: 'Beverages', name: 'Heineken 330ml', company: 'NB Plc', nafdac: 'B2-0891', scans: 8921, fakes: 442, integrity: 95 },
  { cat: 'Pharmaceuticals', name: 'Malar-X 500mg', company: 'Global Pharma Co.', nafdac: 'A3-1122', scans: 6234, fakes: 312, integrity: 85 },
  { cat: 'Beverages', name: 'Eva Water 75cl', company: 'FrieslandCampina', nafdac: 'A1-0428', scans: 5100, fakes: 12, integrity: 99 },
  { cat: 'Electronics', name: 'Samsung S23 Ultra', company: 'Samsung Nigeria', nafdac: 'N/A', scans: 3210, fakes: 8, integrity: 99 },
  { cat: 'Beverages', name: 'Royal Blend Whiskey', company: 'Heritage Spirits', nafdac: 'C1-3300', scans: 4102, fakes: 208, integrity: 90 },
  { cat: 'Personal Care', name: 'Dettol 250ml', company: 'Reckitt Nigeria', nafdac: 'D3-4421', scans: 7891, fakes: 15, integrity: 99 },
  { cat: 'Food', name: 'Indomie Noodles 70g', company: 'De United Foods', nafdac: 'E1-2234', scans: 15442, fakes: 3, integrity: 99 },
];
const EVIDENCE_DATA = [
  { type: 'photo', icon: '📷', title: 'Counterfeit Heineken Batch', desc: '12 photos — Kano Market seizure', date: 'Mar 29, 2026', size: '24.5 MB', case: 'SL-KA-2024' },
  { type: 'video', icon: '🎥', title: 'Raid Footage — Malar-X', desc: '3 videos — Lagos enforcement op', date: 'Mar 28, 2026', size: '412 MB', case: 'SL-LG-2024' },
  { type: 'doc', icon: '📄', title: 'Lab Analysis Report', desc: 'NAFDAC test results — Batch #902', date: 'Mar 27, 2026', size: '1.2 MB', case: 'SL-KA-2024' },
  { type: 'photo', icon: '📷', title: 'Refill Operation Evidence', desc: '8 photos — Port Harcourt', date: 'Mar 25, 2026', size: '18.1 MB', case: 'SL-PH-2024' },
  { type: 'doc', icon: '📄', title: 'Seizure Report Q1 2026', desc: 'Complete enforcement summary', date: 'Mar 20, 2026', size: '3.4 MB', case: 'SL-NAT-Q1' },
  { type: 'video', icon: '🎥', title: 'Vendor Identification Video', desc: '1 video — Ogun border crossing', date: 'Mar 18, 2026', size: '185 MB', case: 'SL-OG-2024' },
];
const NOTIFS_INIT = [
  { text: 'Spike in fake detections in Kano region — Batch SL-KA-2024', time: '2 mins ago', color: '#DC2626', unread: true },
  { text: 'User #881290 flagged for suspicious scanning pattern', time: '8 mins ago', color: '#D97706', unread: true },
  { text: 'Weekly integrity report is ready to download', time: '1 hr ago', color: '#7C3AED', unread: true },
  { text: 'New product registered: Royal Blend Whiskey by Heritage Spirits', time: '3 hrs ago', color: '#059669', unread: false },
  { text: 'System maintenance completed — all services optimal', time: '5 hrs ago', color: '#2563EB', unread: false },
];
const LIVE_PRODUCTS = [
  { icon: '💊', name: 'Paracetamol 500mg', loc: 'Lagos, Ikeja', nafdac: '04-2195', status: 'VALID' },
  { icon: '🍺', name: 'Heineken 330ml', loc: 'Kano, Sabon Gari', nafdac: 'INVALID', status: 'FAKE' },
  { icon: '💧', name: 'Eva Water 75cl', loc: 'Abuja, Garki', nafdac: 'A1-0428', status: 'AUTHENTIC' },
  { icon: '💊', name: 'Malar-X 500mg', loc: 'Kano Market', nafdac: 'INVALID', status: 'FAKE' },
  { icon: '🥛', name: 'Peak Milk 400g', loc: 'Enugu, Trans-Ekulu', nafdac: 'C2-1100', status: 'VALID' },
  { icon: '🧴', name: 'Dettol 250ml', loc: 'Ogun, Abeokuta', nafdac: 'D3-4421', status: 'AUTHENTIC' },
  { icon: '🍜', name: 'Indomie Noodles', loc: 'Lagos, Mushin', nafdac: 'E1-2234', status: 'VALID' },
];
const STATE_RISKS = [
  { state: 'Lagos', count: 1843, color: '#DC2626' },
  { state: 'Kano', count: 1482, color: '#DC2626' },
  { state: 'Rivers', count: 890, color: '#F59E0B' },
  { state: 'Borno', count: 312, color: '#F59E0B' },
  { state: 'Niger', count: 221, color: '#F59E0B' },
];

// ─── HELPERS ─────────────────────────────────────────────────────────────────
const StatusBadge = ({ status }) => {
  const map = {
    FAKE: 'bg-red-100 text-red-600 border-red-200',
    AUTHENTIC: 'bg-green-100 text-green-600 border-green-200',
    VALID: 'bg-blue-100 text-blue-700 border-blue-200',
  };
  return (
    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${map[status] || map.VALID}`}>
      {status}
    </span>
  );
};

const Toast = ({ message, onDone }) => {
  useEffect(() => {
    const t = setTimeout(onDone, 3000);
    return () => clearTimeout(t);
  }, [message, onDone]);
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[9999] bg-gray-900 text-white text-sm px-5 py-3 rounded-xl shadow-xl animate-bounce-in">
      {message}
    </div>
  );
};

const Modal = ({ isOpen, onClose, title, children, actions }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[90vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h3 className="font-bold text-gray-800">{title}</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-lg transition-colors">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>
        <div className="p-6 overflow-y-auto flex-1">{children}</div>
        {actions && <div className="px-6 py-4 border-t border-gray-100 flex gap-3 bg-gray-50">{actions}</div>}
      </div>
    </div>
  );
};

// ─── PAGES ────────────────────────────────────────────────────────────────────
const OverviewPage = ({ scanCount, setModal, showToast }) => {
  const chartData = {
    labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    datasets: [{
      label: 'Fake Detections',
      data: [320, 450, 380, 520, 610, 480, 695],
      borderColor: '#7C3AED',
      backgroundColor: 'rgba(124,58,237,0.08)',
      fill: true,
      tension: 0.4,
      pointRadius: 4,
      pointBackgroundColor: '#7C3AED',
      pointBorderColor: 'white',
      pointBorderWidth: 2,
      borderWidth: 2,
    }],
  };
  const chartOptions = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { backgroundColor: '#111827', titleColor: '#fff', bodyColor: '#9CA3AF', padding: 10, cornerRadius: 8 } },
    scales: { x: { grid: { display: false }, ticks: { color: '#9CA3AF', font: { size: 11 } } }, y: { grid: { color: 'rgba(229,231,235,0.8)' }, ticks: { color: '#9CA3AF', font: { size: 11 } } } },
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">National Integrity Overview</h1>
        <p className="text-gray-400 text-sm mt-1">Real-time product authentication monitoring across Nigerian regions.</p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Users', value: '1.2M', badge: '↑ 12%', up: true },
          { label: 'Scans Today', value: scanCount.toLocaleString(), badge: '↑ 8%', up: true },
          { label: 'Verified Authentic', value: '88.4%', badge: 'Below Target', up: false, warn: true },
          { label: 'Detected Fakes', value: '4,902', badge: '▲ +5%', up: false, danger: true },
        ].map((s, i) => (
          <div key={i} className={`bg-white rounded-2xl p-5 shadow-soft border ${s.danger ? 'border-red-100' : 'border-gray-100'}`}>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">{s.label}</p>
            <p className={`text-2xl font-bold mb-2 ${s.danger ? 'text-red-500' : 'text-gray-900'}`}>{s.value}</p>
            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${s.up ? 'bg-green-100 text-green-600' : s.danger ? 'bg-red-100 text-red-500' : 'bg-amber-100 text-amber-600'}`}>
              {s.badge}
            </span>
          </div>
        ))}
      </div>

      {/* Chart + State Risk */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-2xl p-5 shadow-soft border border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-gray-800">Fake Detection Trend</h3>
            <span className="text-xs text-gray-400">Last 7 days</span>
          </div>
          <div style={{ height: 220 }}>
            <Line data={chartData} options={chartOptions} />
          </div>
        </div>
        <div className="bg-white rounded-2xl p-5 shadow-soft border border-gray-100">
          <h3 className="font-bold text-gray-800 mb-4">Top Risk States</h3>
          <div className="space-y-3">
            {STATE_RISKS.map((s, i) => (
              <div key={i} className="flex items-center gap-3 cursor-pointer hover:bg-gray-50 rounded-xl p-2 -mx-2 transition-colors"
                onClick={() => showToast(`Viewing ${s.state} details`)}>
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: s.color }} />
                <span className="text-sm text-gray-700 flex-1">{s.state}</span>
                <span className="text-sm font-bold" style={{ color: s.color }}>{s.fakes || s.count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Live Feed */}
      <div className="bg-white rounded-2xl shadow-soft border border-gray-100 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-50">
          <h3 className="font-bold text-gray-800">Live Scan Feed</h3>
          <button onClick={() => setModal('viewAll')} className="text-primary text-sm font-semibold hover:underline">View All →</button>
        </div>
        <div className="divide-y divide-gray-50">
          {SCANS_DATA.slice(0, 5).map((s, i) => (
            <div key={i} className={`flex items-center gap-3 px-5 py-3 cursor-pointer hover:bg-gray-50 transition-colors ${s.status === 'FAKE' ? 'bg-red-50/50' : ''}`}
              onClick={() => setModal('scan', s)}>
              <span className="text-xl">{s.icon}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{s.product}</p>
                <p className="text-xs text-gray-400">{s.location} · {s.time}</p>
              </div>
              <StatusBadge status={s.status} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const UsersPage = ({ showToast }) => {
  const [selected, setSelected] = useState(0);
  const [scanFilter, setScanFilter] = useState('ALL');
  const u = USERS_DATA[selected];
  const filteredScans = scanFilter === 'ALL' ? SCANS_DATA
    : scanFilter === 'ORIGINAL' ? SCANS_DATA.filter(s => s.status !== 'FAKE')
    : SCANS_DATA.filter(s => s.status === scanFilter);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* User Table */}
        <div className="lg:col-span-2 bg-white rounded-2xl shadow-soft border border-gray-100 overflow-hidden">
          <table className="w-full">
            <thead><tr className="border-b border-gray-100">
              {['User', 'Phone', 'Score', 'Scans', 'Last Active'].map(h => (
                <th key={h} className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 py-3">{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {USERS_DATA.map((u, i) => (
                <tr key={i} onClick={() => setSelected(i)}
                  className={`border-b border-gray-50 cursor-pointer transition-colors ${selected === i ? 'bg-primary/5' : 'hover:bg-gray-50'}`}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0" style={{ background: u.color }}>{u.initials}</div>
                      <span className="text-sm font-medium text-gray-800">{u.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">{u.phone}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-bold px-2 py-1 rounded-full ${u.score >= 80 ? 'bg-green-100 text-green-600' : u.score >= 50 ? 'bg-amber-100 text-amber-600' : 'bg-red-100 text-red-500'}`}>{u.score}</span>
                  </td>
                  <td className="px-4 py-3 text-sm font-medium text-gray-700">{u.scans.toLocaleString()}</td>
                  <td className="px-4 py-3 text-xs text-gray-400">{u.lastActive}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* User Detail */}
        <div className="bg-white rounded-2xl shadow-soft border border-gray-100 p-5">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-full flex items-center justify-center text-white font-bold" style={{ background: u.color }}>{u.initials}</div>
            <div>
              <p className="font-bold text-gray-800">{u.name}</p>
              <p className="text-xs text-gray-400">{u.tier}</p>
            </div>
          </div>
          {[['Rep Score', u.rep + '%'], ['Earned', u.earned], ['Total Scans', u.scans.toLocaleString()]].map(([l, v]) => (
            <div key={l} className="flex justify-between py-2 border-b border-gray-50">
              <span className="text-xs text-gray-400">{l}</span>
              <span className="text-xs font-semibold text-gray-700">{v}</span>
            </div>
          ))}
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mt-4 mb-2">Recent Activity</p>
          <div className="space-y-2">
            {u.activity.map((a, i) => (
              <div key={i} className="flex gap-2 text-xs">
                <span>{a.icon}</span>
                <div>
                  <p className="font-medium text-gray-700">{a.text}</p>
                  <p className="text-gray-400">{a.loc} · {a.time}</p>
                </div>
              </div>
            ))}
          </div>
          <button onClick={() => showToast('Message sent to curator')} className="mt-4 w-full bg-primary text-white text-sm font-semibold py-2.5 rounded-xl hover:bg-primary/90 transition-colors">
            Contact Curator
          </button>
        </div>
      </div>
      {/* Scan Stream */}
      <div className="bg-white rounded-2xl shadow-soft border border-gray-100 overflow-hidden">
        <div className="flex items-center gap-2 px-5 py-4 border-b border-gray-100">
          {['ALL', 'FAKE', 'AUTHENTIC', 'ORIGINAL'].map(f => (
            <button key={f} onClick={() => setScanFilter(f)}
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors ${scanFilter === f ? 'bg-primary text-white' : 'text-gray-500 hover:bg-gray-100'}`}>
              {f}
            </button>
          ))}
        </div>
        <div className="divide-y divide-gray-50">
          {filteredScans.map((s, i) => (
            <div key={i} className="flex items-center gap-3 px-5 py-3">
              <span className="text-lg">{s.icon}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{s.product}</p>
                <p className="text-xs text-gray-400">{s.nafdac} — {s.location}</p>
              </div>
              <StatusBadge status={s.status} />
              <div className="text-right text-xs text-gray-400 min-w-max">
                <p className="uppercase">User</p>
                <p className="font-bold text-gray-700">{s.user}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const ScansPage = ({ setModal }) => {
  const [filter, setFilter] = useState('all');
  const filtered = filter === 'all' ? SCANS_DATA : SCANS_DATA.filter(s => s.status === filter);
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Scan History</h1>
          <p className="text-gray-400 text-sm mt-1">Complete scan log across all regions and users.</p>
        </div>
      </div>
      <div className="bg-white rounded-2xl shadow-soft border border-gray-100 overflow-hidden">
        <div className="flex items-center gap-2 px-5 py-4 border-b border-gray-100">
          {['all', 'FAKE', 'AUTHENTIC', 'VALID'].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors ${filter === f ? 'bg-primary text-white' : 'text-gray-500 hover:bg-gray-100'}`}>
              {f.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr className="border-b border-gray-100">
              {['Product', 'NAFDAC', 'Location', 'User', 'Status', 'Time'].map(h => (
                <th key={h} className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 py-3">{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {filtered.map((s, i) => (
                <tr key={i} onClick={() => setModal('scan', s)}
                  className="border-b border-gray-50 cursor-pointer hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-sm font-medium text-gray-800"><span className="mr-2">{s.icon}</span>{s.product}</td>
                  <td className="px-4 py-3 text-xs" style={{ color: s.nafdac === 'INVALID' ? '#DC2626' : '#6B7280' }}>{s.nafdac}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">{s.location}</td>
                  <td className="px-4 py-3 text-xs font-medium text-gray-700">{s.user}</td>
                  <td className="px-4 py-3"><StatusBadge status={s.status} /></td>
                  <td className="px-4 py-3 text-xs text-gray-400">{s.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

const ProductsPage = ({ showToast }) => (
  <div className="space-y-6">
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Product Registry</h1>
        <p className="text-gray-400 text-sm mt-1">All registered products and integrity scores.</p>
      </div>
      <button onClick={() => showToast('Registration form opened')} className="bg-primary text-white text-sm font-semibold px-4 py-2.5 rounded-xl hover:bg-primary/90 transition-colors flex items-center gap-2">
        <Package className="w-4 h-4" /> Register Product
      </button>
    </div>
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {PRODUCTS_DATA.map((p, i) => {
        const ic = p.integrity >= 98 ? '#059669' : p.integrity >= 90 ? '#D97706' : '#DC2626';
        return (
          <div key={i} onClick={() => showToast(`Viewing ${p.name}`)}
            className="bg-white rounded-2xl p-5 shadow-soft border border-gray-100 cursor-pointer hover:border-primary/30 hover:shadow-md transition-all">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest bg-gray-100 px-2 py-0.5 rounded-md">{p.cat}</span>
            <p className="font-bold text-gray-800 mt-2 mb-1">{p.name}</p>
            <p className="text-xs text-gray-400 mb-3">{p.company}</p>
            <p className="text-[11px] text-gray-400 mb-3">NAFDAC: {p.nafdac}</p>
            <div className="flex justify-between text-center border-t border-gray-50 pt-3">
              {[['Scans', p.scans.toLocaleString(), 'text-gray-700'], ['Fakes', p.fakes, p.fakes > 100 ? 'text-red-500' : 'text-gray-700'], ['Integrity', `${p.integrity}%`, '']].map(([l, v, cls]) => (
                <div key={l}>
                  <p className="text-[10px] text-gray-400 uppercase tracking-wider">{l}</p>
                  <p className={`text-sm font-bold ${cls}`} style={l === 'Integrity' ? { color: ic } : {}}>{v}</p>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  </div>
);

const HeatMapPage = ({ showToast }) => (
  <div className="space-y-6">
    <h1 className="text-2xl font-bold text-gray-900">Heat Map Analytics</h1>
    <div className="bg-white rounded-2xl shadow-soft border border-gray-100 p-6">
      <div className="flex items-center gap-2 mb-4">
        {['All', 'Authentic', 'Fake'].map(f => (
          <button key={f} onClick={() => showToast(`Map filter: ${f}`)}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-gray-100 text-gray-600 hover:bg-primary hover:text-white transition-colors">
            {f}
          </button>
        ))}
      </div>
      {/* SVG Nigeria map placeholder */}
      <div className="relative bg-gradient-to-br from-gray-50 to-slate-100 rounded-2xl" style={{ height: 380 }}>
        <svg viewBox="0 0 600 500" className="w-full h-full opacity-60">
          <ellipse cx="300" cy="250" rx="220" ry="180" fill="#e5e7eb" stroke="#d1d5db" strokeWidth="2" />
          <text x="300" y="255" textAnchor="middle" className="text-gray-400" fontSize="14" fill="#9CA3AF">Nigeria Map</text>
        </svg>
        {/* Risk pins */}
        {[
          { label: 'Lagos', x: '22%', y: '65%', color: '#DC2626', count: '1,843' },
          { label: 'Kano', x: '46%', y: '25%', color: '#DC2626', count: '1,482' },
          { label: 'Rivers', x: '38%', y: '72%', color: '#F59E0B', count: '890' },
          { label: 'Abuja', x: '44%', y: '48%', color: '#059669', count: '12' },
          { label: 'Borno', x: '68%', y: '20%', color: '#DC2626', count: '312' },
        ].map((p, i) => (
          <div key={i} onClick={() => showToast(`${p.label}: ${p.count} fakes detected`)}
            className="absolute flex flex-col items-center cursor-pointer group" style={{ left: p.x, top: p.y, transform: 'translate(-50%,-50%)' }}>
            <div className="w-5 h-5 rounded-full border-2 border-white shadow-md group-hover:scale-125 transition-transform" style={{ background: p.color }} />
            <div className="opacity-0 group-hover:opacity-100 transition-opacity bg-gray-900 text-white text-[10px] px-2 py-1 rounded-lg mt-1 whitespace-nowrap">
              {p.label}: {p.count}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 grid grid-cols-3 gap-4 text-center">
        {[['Critical Risk', '#DC2626', '3 states'], ['High Risk', '#F59E0B', '4 states'], ['Low Risk', '#059669', '29 states']].map(([l, c, v]) => (
          <div key={l} className="flex flex-col items-center gap-1">
            <div className="w-3 h-3 rounded-full" style={{ background: c }} />
            <p className="text-xs text-gray-400">{l}</p>
            <p className="text-sm font-bold text-gray-700">{v}</p>
          </div>
        ))}
      </div>
    </div>
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {[['National Fake Rate', '11.6%', '↑ 2.3% this week'], ['Highest Alert Zone', 'Lagos', '1,843 fakes this month'], ['Active Enforcement', '14 Teams', 'Deployed across 6 states']].map(([l, v, s]) => (
        <div key={l} className="bg-white rounded-2xl p-5 shadow-soft border border-gray-100">
          <p className="text-xs text-gray-400 mb-1">{l}</p>
          <p className="text-xl font-bold text-gray-800 mb-1">{v}</p>
          <p className="text-xs text-gray-400">{s}</p>
        </div>
      ))}
    </div>
    <button onClick={() => showToast('Regional raid order initiated — Lagos Command notified')}
      className="w-full bg-red-500 hover:bg-red-600 text-white font-bold py-3 rounded-xl transition-colors flex items-center justify-center gap-2">
      <AlertTriangle className="w-4 h-4" /> INITIATE REGIONAL RAID ORDER
    </button>
  </div>
);

const EvidencePage = ({ showToast }) => {
  const typeStyle = { photo: 'bg-blue-100 text-blue-600', video: 'bg-purple-100 text-purple-600', doc: 'bg-green-100 text-green-600' };
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Evidence Vault</h1>
          <p className="text-gray-400 text-sm mt-1">Secure storage for counterfeit evidence files and audit trails.</p>
        </div>
        <button onClick={() => showToast('Upload dialog opened')} className="bg-primary text-white text-sm font-semibold px-4 py-2.5 rounded-xl hover:bg-primary/90 transition-colors">
          + Upload Evidence
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {EVIDENCE_DATA.map((e, i) => (
          <div key={i} onClick={() => showToast(`Opening: ${e.title}`)}
            className="bg-white rounded-2xl p-5 shadow-soft border border-gray-100 cursor-pointer hover:border-primary/30 hover:shadow-md transition-all">
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${typeStyle[e.type]}`}>{e.icon} {e.type.toUpperCase()}</span>
            <p className="font-bold text-gray-800 mt-2 mb-1">{e.title}</p>
            <p className="text-xs text-gray-400 mb-3">{e.desc}</p>
            <div className="flex justify-between text-xs text-gray-400 border-t border-gray-50 pt-3">
              <span>Case: {e.case}</span>
              <span>{e.size}</span>
            </div>
            <p className="text-[11px] text-gray-400 mt-1">{e.date}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

const SettingsPage = ({ showToast }) => {
  const [name, setName] = useState('Admin Curator');
  const [role, setRole] = useState('Integrity Officer');
  return (
    <div className="space-y-6 max-w-lg">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
      <div className="bg-white rounded-2xl shadow-soft border border-gray-100 p-6 space-y-4">
        <h3 className="font-bold text-gray-800 border-b border-gray-50 pb-3">Account Settings</h3>
        {[['Full Name', name, setName], ['Role', role, setRole]].map(([l, v, fn]) => (
          <div key={l}>
            <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1 block">{l}</label>
            <input value={v} onChange={e => fn(e.target.value)}
              className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary text-sm" />
          </div>
        ))}
        <button onClick={() => showToast('Settings saved successfully')}
          className="bg-primary text-white text-sm font-semibold px-5 py-2.5 rounded-xl hover:bg-primary/90 transition-colors">
          Save Changes
        </button>
      </div>
      <div className="bg-white rounded-2xl shadow-soft border border-gray-100 p-6 space-y-4">
        <h3 className="font-bold text-gray-800 border-b border-gray-50 pb-3">Notification Preferences</h3>
        {[['Fake detection alerts', true], ['Weekly report emails', false], ['Live scan notifications', true]].map(([l, on]) => (
          <div key={l} className="flex items-center justify-between">
            <span className="text-sm text-gray-700">{l}</span>
            <button onClick={() => showToast(`Preference updated`)}
              className={`w-11 h-6 rounded-full transition-colors relative ${on ? 'bg-primary' : 'bg-gray-200'}`}>
              <div className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow-sm transition-all ${on ? 'left-6' : 'left-1'}`} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

const SupportPage = ({ showToast }) => (
  <div className="space-y-6 max-w-lg">
    <h1 className="text-2xl font-bold text-gray-900">Support</h1>
    <div className="bg-white rounded-2xl shadow-soft border border-gray-100 p-6 space-y-4">
      <h3 className="font-bold text-gray-800 border-b border-gray-50 pb-3">Contact Support</h3>
      <div>
        <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1 block">Issue Category</label>
        <select className="w-full px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary bg-white">
          {['Technical Issue', 'Account Access', 'Data Discrepancy', 'Feature Request'].map(o => <option key={o}>{o}</option>)}
        </select>
      </div>
      <div>
        <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1 block">Description</label>
        <textarea className="w-full px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-none h-28" placeholder="Describe your issue…" />
      </div>
      <button onClick={() => showToast('Support ticket submitted — response within 2 hours')}
        className="bg-primary text-white text-sm font-semibold px-5 py-2.5 rounded-xl hover:bg-primary/90 transition-colors">
        Submit Ticket
      </button>
    </div>
  </div>
);

// ─── MAIN DASHBOARD ───────────────────────────────────────────────────────────
const AdminDashboard = () => {
  const navigate = useNavigate();

  // Auth guard
  useEffect(() => {
    const auth = JSON.parse(localStorage.getItem('adminAuth') || '{}');
    if (!auth.authenticated) navigate('/admin', { replace: true });
  }, [navigate]);

  const [page, setPage] = useState('overview');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const [notifs, setNotifs] = useState(NOTIFS_INIT);
  const [notifOpen, setNotifOpen] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [modal, setModalState] = useState({ type: null, data: null });
  const [scanCount, setScanCount] = useState(42893);
  const [reportType, setReportType] = useState('National Overview');

  const showToast = useCallback((msg) => setToast(msg), []);
  const setModal = useCallback((type, data = null) => setModalState({ type, data }), []);
  const closeModal = useCallback(() => setModalState({ type: null, data: null }), []);

  // Live feed simulation
  useEffect(() => {
    const interval = setInterval(() => {
      setScanCount(c => c + Math.floor(Math.random() * 3 + 1));
      const p = LIVE_PRODUCTS[Math.floor(Math.random() * LIVE_PRODUCTS.length)];
      if (p.status === 'FAKE') {
        setNotifs(prev => [
          { text: `New fake: ${p.name} at ${p.loc}`, time: 'just now', color: '#DC2626', unread: true },
          ...prev.slice(0, 9),
        ]);
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('adminAuth');
    navigate('/admin');
  };

  const unreadCount = notifs.filter(n => n.unread).length;

  const navItems = [
    { id: 'overview', icon: LayoutGrid, label: 'Overview' },
    { id: 'users', icon: Users, label: 'User Management' },
    { id: 'scans', icon: Clock, label: 'Scan History' },
    { id: 'products', icon: Package, label: 'Product Registry' },
    { id: 'heatmap', icon: Map, label: 'Heat Map Analytics' },
    { id: 'vault', icon: Shield, label: 'Evidence Vault' },
  ];
  const bottomItems = [
    { id: 'settings', icon: Settings, label: 'Settings' },
    { id: 'support', icon: HelpCircle, label: 'Support' },
  ];

  const SEARCH_INDEX = [
    ...USERS_DATA.map(u => ({ title: u.name, sub: u.phone, page: 'users', icon: '👤' })),
    ...PRODUCTS_DATA.map(p => ({ title: p.name, sub: p.company, page: 'products', icon: '📦' })),
    ...SCANS_DATA.map(s => ({ title: s.product, sub: `${s.location} — ${s.status}`, page: 'scans', icon: '🔍' })),
  ];
  const searchResults = searchQ.trim().length > 0
    ? SEARCH_INDEX.filter(i => i.title.toLowerCase().includes(searchQ.toLowerCase()) || i.sub.toLowerCase().includes(searchQ.toLowerCase())).slice(0, 6)
    : [];

  const Sidebar = ({ mobile = false }) => (
    <div className={`flex flex-col h-full bg-white border-r border-gray-100 ${mobile ? 'w-64' : 'w-64'}`}>
      {/* Brand */}
      <div className="flex items-center justify-between p-6 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">
            <Shield className="w-5 h-5 text-primary" />
          </div>
          <div>
            <span className="font-syne font-bold text-lg">Sabi<span className="text-primary">Lens</span></span>
            <p className="text-[10px] text-gray-400 leading-none">Product Integrity</p>
          </div>
        </div>
        {mobile && <button onClick={() => setSidebarOpen(false)} className="p-1 hover:bg-gray-100 rounded-lg"><X className="w-5 h-5 text-gray-400" /></button>}
      </div>

      {/* Generate Report */}
      <div className="px-4 pt-4">
        <button onClick={() => setModal('report')}
          className="w-full bg-primary text-white text-sm font-semibold py-2.5 rounded-xl hover:bg-primary/90 transition-colors">
          Generate Report
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {navItems.map(({ id, icon: Icon, label }) => (
          <button key={id} onClick={() => { setPage(id); if (mobile) setSidebarOpen(false); }}
            className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-sm font-medium ${page === id ? 'bg-primary/10 text-primary' : 'text-gray-500 hover:bg-gray-50'}`}>
            <Icon className="w-5 h-5 flex-shrink-0" />
            {label}
          </button>
        ))}
      </nav>

      {/* Bottom nav */}
      <div className="p-4 border-t border-gray-100 space-y-1">
        {bottomItems.map(({ id, icon: Icon, label }) => (
          <button key={id} onClick={() => { setPage(id); if (mobile) setSidebarOpen(false); }}
            className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-sm font-medium ${page === id ? 'bg-primary/10 text-primary' : 'text-gray-500 hover:bg-gray-50'}`}>
            <Icon className="w-5 h-5 flex-shrink-0" />
            {label}
          </button>
        ))}
        <button onClick={handleLogout}
          className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium text-red-400 hover:bg-red-50 transition-colors">
          <LogOut className="w-5 h-5" /> Logout
        </button>
      </div>
    </div>
  );

  const pageEl = {
    overview: <OverviewPage scanCount={scanCount} setModal={setModal} showToast={showToast} />,
    users: <UsersPage showToast={showToast} />,
    scans: <ScansPage setModal={setModal} />,
    products: <ProductsPage showToast={showToast} />,
    heatmap: <HeatMapPage showToast={showToast} />,
    vault: <EvidencePage showToast={showToast} />,
    settings: <SettingsPage showToast={showToast} />,
    support: <SupportPage showToast={showToast} />,
  }[page];

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Desktop Sidebar */}
      <div className="hidden lg:flex flex-col h-screen fixed left-0 top-0 w-64 shadow-soft z-30">
        <Sidebar />
      </div>

      {/* Mobile Sidebar */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />
          <div className="absolute left-0 top-0 h-full shadow-2xl">
            <Sidebar mobile />
          </div>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 flex flex-col lg:ml-64 min-h-0">
        {/* Topbar */}
        <header className="bg-white border-b border-gray-100 px-4 lg:px-6 py-3 flex items-center gap-3 flex-shrink-0 sticky top-0 z-20">
          <button className="lg:hidden p-2 hover:bg-gray-100 rounded-xl" onClick={() => setSidebarOpen(true)}>
            <Menu className="w-5 h-5 text-gray-500" />
          </button>

          {/* Search */}
          <div className="flex-1 relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              value={searchQ}
              onChange={e => setSearchQ(e.target.value)}
              placeholder="Search users, products, scans…"
              className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary bg-gray-50"
            />
            {searchResults.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-xl shadow-xl border border-gray-100 z-50 overflow-hidden">
                {searchResults.map((r, i) => (
                  <button key={i} onClick={() => { setPage(r.page); setSearchQ(''); }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 transition-colors text-left">
                    <span className="text-base">{r.icon}</span>
                    <div>
                      <p className="text-sm font-medium text-gray-800">{r.title}</p>
                      <p className="text-xs text-gray-400">{r.sub}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 ml-auto">
            {/* Notifications */}
            <div className="relative">
              <button onClick={() => setNotifOpen(o => !o)} className="relative p-2 hover:bg-gray-100 rounded-xl">
                <Bell className="w-5 h-5 text-gray-500" />
                {unreadCount > 0 && <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />}
              </button>
              {notifOpen && (
                <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-2xl shadow-xl border border-gray-100 z-50 overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                    <span className="font-semibold text-sm text-gray-800">Notifications</span>
                    <button onClick={() => { setNotifs(n => n.map(x => ({ ...x, unread: false }))); showToast('All marked as read'); }}
                      className="text-xs text-primary hover:underline">Mark all read</button>
                  </div>
                  <div className="max-h-72 overflow-y-auto">
                    {notifs.map((n, i) => (
                      <div key={i} onClick={() => setNotifs(prev => prev.map((x, j) => j === i ? { ...x, unread: false } : x))}
                        className={`flex items-start gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 border-b border-gray-50 ${n.unread ? 'bg-blue-50/30' : ''}`}>
                        <div className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0" style={{ background: n.color }} />
                        <div>
                          <p className="text-xs text-gray-700">{n.text}</p>
                          <p className="text-[10px] text-gray-400 mt-0.5">{n.time}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* User chip */}
            <button onClick={() => setPage('settings')}
              className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-100 rounded-xl transition-colors">
              <div className="text-right hidden sm:block">
                <p className="text-xs font-semibold text-gray-700">Admin Curator</p>
                <p className="text-[10px] text-gray-400">Integrity Officer</p>
              </div>
              <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center">
                <span className="text-primary text-xs font-bold">AC</span>
              </div>
            </button>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6" onClick={() => { setNotifOpen(false); if (searchQ) setSearchQ(''); }}>
          {pageEl}
        </main>
      </div>

      {/* Modals */}
      {/* Scan Detail Modal */}
      <Modal isOpen={modal.type === 'scan'} onClose={closeModal} title="Scan Detail"
        actions={
          <>
            <button onClick={closeModal} className="flex-1 border border-gray-200 text-gray-600 text-sm font-semibold py-2.5 rounded-xl hover:bg-gray-50 transition-colors">Close</button>
            <button onClick={() => { showToast('Evidence logged to vault'); closeModal(); }} className="flex-1 bg-primary text-white text-sm font-semibold py-2.5 rounded-xl hover:bg-primary/90 transition-colors">Log Evidence</button>
          </>
        }>
        {modal.data && (() => {
          const s = modal.data;
          const isFake = s.status === 'FAKE';
          return (
            <div className="space-y-3">
              <div className={`text-center py-3 rounded-xl font-bold text-lg ${isFake ? 'bg-red-100 text-red-600' : s.status === 'AUTHENTIC' ? 'bg-green-100 text-green-600' : 'bg-blue-100 text-blue-600'}`}>
                {isFake ? '🚫 FAKE' : s.status === 'AUTHENTIC' ? '✅ AUTHENTIC' : '✓ VALID'}
              </div>
              {[['Product', s.product], ['NAFDAC Code', s.nafdac], ['Location', s.location], ['User ID', s.user], ['Scan Time', s.time]].map(([l, v]) => (
                <div key={l} className="flex justify-between py-2 border-b border-gray-50">
                  <span className="text-xs text-gray-400">{l}</span>
                  <span className="text-xs font-semibold" style={{ color: l === 'NAFDAC Code' && v === 'INVALID' ? '#DC2626' : 'inherit' }}>{v}</span>
                </div>
              ))}
              {isFake && <div className="bg-red-50 border border-red-100 rounded-xl p-3 text-xs text-red-600">⚠ This product has been flagged as counterfeit. Please log evidence immediately.</div>}
            </div>
          );
        })()}
      </Modal>

      {/* View All Scans */}
      <Modal isOpen={modal.type === 'viewAll'} onClose={closeModal} title="All Recent Scans"
        actions={
          <>
            <button onClick={closeModal} className="flex-1 border border-gray-200 text-gray-600 text-sm font-semibold py-2.5 rounded-xl hover:bg-gray-50 transition-colors">Close</button>
            <button onClick={() => { setPage('scans'); closeModal(); }} className="flex-1 bg-primary text-white text-sm font-semibold py-2.5 rounded-xl hover:bg-primary/90 transition-colors">View Full History →</button>
          </>
        }>
        <div className="space-y-2">
          {SCANS_DATA.map((s, i) => (
            <div key={i} onClick={() => setModal('scan', s)}
              className="flex items-center gap-3 p-3 rounded-xl hover:bg-gray-50 cursor-pointer transition-colors">
              <span className="text-lg">{s.icon}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{s.product}</p>
                <p className="text-xs text-gray-400">{s.user} · {s.time}</p>
              </div>
              <StatusBadge status={s.status} />
            </div>
          ))}
        </div>
      </Modal>

      {/* Generate Report */}
      <Modal isOpen={modal.type === 'report'} onClose={closeModal} title="Generate Report"
        actions={
          <>
            <button onClick={closeModal} className="flex-1 border border-gray-200 text-gray-600 text-sm font-semibold py-2.5 rounded-xl hover:bg-gray-50 transition-colors">Cancel</button>
            <button onClick={() => { closeModal(); showToast(`Generating "${reportType}"…`); setTimeout(() => showToast('Report ready — download started'), 2000); }}
              className="flex-1 bg-primary text-white text-sm font-semibold py-2.5 rounded-xl hover:bg-primary/90 transition-colors">Generate & Download</button>
          </>
        }>
        <div className="space-y-4">
          <p className="text-sm text-gray-500">Select report type:</p>
          <div className="grid grid-cols-2 gap-3">
            {[['🗺️', 'National Overview', 'All 36 states summary'], ['🚫', 'Fake Activity Log', 'Detailed counterfeit records'], ['👤', 'User Performance', 'Curator scores & activity'], ['🔐', 'Evidence Summary', 'Vault contents & seizures']].map(([icon, type, sub]) => (
              <button key={type} onClick={() => setReportType(type)}
                className={`p-3 rounded-xl border text-left transition-all ${reportType === type ? 'border-primary bg-primary/5' : 'border-gray-200 hover:border-gray-300'}`}>
                <p className="text-xl mb-1">{icon}</p>
                <p className="text-xs font-bold text-gray-800">{type}</p>
                <p className="text-[10px] text-gray-400">{sub}</p>
              </button>
            ))}
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1 block">Time Range</label>
            <select className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 bg-white">
              {['Last 24 Hours', 'Last 7 Days', 'Last 30 Days', 'This Quarter'].map(o => <option key={o}>{o}</option>)}
            </select>
          </div>
        </div>
      </Modal>

      {/* Toast */}
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </div>
  );
};

export default AdminDashboard;