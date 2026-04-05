import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, Eye, EyeOff, Lock, User, AlertCircle } from 'lucide-react';

// Admin credentials (in a real app, this would be server-side auth)
const ADMIN_CREDENTIALS = {
  username: 'admin',
  password: 'SabiLens@Admin2026',
};

const AdminLogin = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [touched, setTouched] = useState({});

  const handleChange = (e) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
    setError('');
  };

  const handleBlur = (field) => setTouched(prev => ({ ...prev, [field]: true }));

  const handleSubmit = (e) => {
    e.preventDefault();
    setTouched({ username: true, password: true });
    if (!form.username || !form.password) return;

    setLoading(true);
    setError('');

    setTimeout(() => {
      if (
        form.username === ADMIN_CREDENTIALS.username &&
        form.password === ADMIN_CREDENTIALS.password
      ) {
        localStorage.setItem('adminAuth', JSON.stringify({ authenticated: true, loginTime: Date.now() }));
        navigate('/admin/dashboard');
      } else {
        setError('Invalid username or password. Please try again.');
        setLoading(false);
      }
    }, 1000);
  };

  const fieldClass = (field) => {
    const base = 'w-full pl-11 pr-4 py-3 border rounded-xl focus:outline-none focus:ring-2 transition-all duration-200 text-sm font-sans bg-white';
    if (touched[field] && !form[field]) return `${base} border-red-300 bg-red-50 focus:ring-red-200 focus:border-red-400`;
    if (touched[field] && form[field]) return `${base} border-primary bg-primary/5 focus:ring-primary/20 focus:border-primary`;
    return `${base} border-gray-200 focus:border-primary focus:ring-primary/20`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-950 to-slate-900 flex items-center justify-center p-4">
      {/* Ambient background blobs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-md relative z-10">
        {/* Card */}
        <div className="bg-white rounded-3xl shadow-2xl overflow-hidden">
          {/* Header band */}
          <div className="bg-gradient-to-r from-slate-900 to-purple-950 px-8 pt-8 pb-6 text-center">
            <div className="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-white/20">
              <ShieldCheck className="w-8 h-8 text-primary" />
            </div>
            <h1 className="font-syne font-bold text-2xl text-white tracking-tight mb-1">
              Sabi<span className="text-primary">Lens</span>
            </h1>
            <p className="text-white/50 text-xs font-mono uppercase tracking-widest">
              Admin · Integrity Control
            </p>
          </div>

          {/* Form */}
          <div className="px-8 py-8">
            <h2 className="font-bold text-gray-800 text-lg mb-1">Sign in to Admin</h2>
            <p className="text-gray-400 text-sm mb-6">Restricted access. Authorised personnel only.</p>

            {/* Error banner */}
            {error && (
              <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-600 text-sm px-4 py-3 rounded-xl mb-5">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Username */}
              <div>
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5 block">
                  Username
                </label>
                <div className="relative">
                  <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    name="username"
                    value={form.username}
                    onChange={handleChange}
                    onBlur={() => handleBlur('username')}
                    placeholder="Enter admin username"
                    autoComplete="username"
                    className={fieldClass('username')}
                  />
                </div>
                {touched.username && !form.username && (
                  <p className="text-red-500 text-xs mt-1">Username is required</p>
                )}
              </div>

              {/* Password */}
              <div>
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5 block">
                  Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    value={form.password}
                    onChange={handleChange}
                    onBlur={() => handleBlur('password')}
                    placeholder="Enter admin password"
                    autoComplete="current-password"
                    className={`${fieldClass('password')} pr-11`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-primary transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {touched.password && !form.password && (
                  <p className="text-red-500 text-xs mt-1">Password is required</p>
                )}
              </div>

              {/* Submit */}
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-primary hover:bg-primary/90 text-white font-semibold py-3 px-6 rounded-xl transition-all duration-200 shadow-soft flex items-center justify-center gap-2 mt-2 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                    </svg>
                    Authenticating…
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-4 h-4" />
                    Sign In
                  </>
                )}
              </button>
            </form>

            {/* Footer note */}
            <p className="text-center text-xs text-gray-400 mt-6">
              Unauthorised access is a violation of SabiLens security policy.
            </p>
          </div>
        </div>

        {/* Back link */}
        <button
          onClick={() => navigate('/landing')}
          className="flex items-center gap-1.5 text-white/50 hover:text-white/80 text-sm transition-colors mx-auto mt-5"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 5l-7 7 7 7"/>
          </svg>
          Back to landing page
        </button>
      </div>
    </div>
  );
};

export default AdminLogin;