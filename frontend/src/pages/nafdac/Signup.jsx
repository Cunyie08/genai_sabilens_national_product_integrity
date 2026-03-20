import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Icon from '../../components/common/Icon';
import Card from '../../components/common/Card';
import Button from '../../components/common/Button';
import Modal from '../../components/common/Modal';
import { authApi } from '../../services/api';

const NAFDACSignup = () => {
    const navigate = useNavigate();
    const [formData, setFormData] = useState({
        firstName: '',
        lastName: '',
        officialEmail: '',
        phone: '',
        officerId: '',
        department: '',
        password: '',
        confirmPassword: '',
        agreeTerms: false
    });

    const [touched, setTouched] = useState({});
    const [showTermsModal, setShowTermsModal] = useState(false);
    const [showPrivacyModal, setShowPrivacyModal] = useState(false);
    const [modalOpen, setModalOpen] = useState(false);
    const [modalConfig, setModalConfig] = useState({
        type: 'success',
        title: '',
        message: ''
    });

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        if (name === 'phone') {
            setFormData(prev => ({ ...prev, phone: value.replace(/\D/g, '') }));
        } else {
            setFormData(prev => ({
                ...prev,
                [name]: type === 'checkbox' ? checked : value
            }));
        }
    };

    const handleBlur = (name) => {
        setTouched(prev => ({ ...prev, [name]: true }));
    };

    const validateField = (name, value) => {
        switch (name) {
            case 'firstName': return value ? '' : 'First name is required';
            case 'lastName': return value ? '' : 'Last name is required';
            case 'officialEmail':
                if (!value) return 'Official email is required';
                if (!value.endsWith('.gov.ng') && !value.endsWith('nafdac.gov.ng')) {
                    return 'Must be an official .gov.ng email';
                }
                return '';
            case 'phone':
                return /^[0-9]{10}$/.test(value) ? '' : 'Valid 10-digit phone number required';
            case 'officerId': return value ? '' : 'Officer ID is required';
            case 'password':
                if (!value) return 'Password is required';
                if (value.length < 8) return 'Password must be at least 8 characters';
                return '';
            case 'confirmPassword':
                if (value !== formData.password) return 'Passwords do not match';
                return '';
            case 'agreeTerms':
                return value ? '' : 'You must agree to the regulatory terms';
            default:
                return '';
        }
    };

    const getFieldError = (name) => {
        if (!touched[name]) return '';
        return validateField(name, formData[name]);
    };

    const isFormValid = () => {
        return Object.keys(formData).every(key => !validateField(key, formData[key]));
    };

    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setTouched(Object.keys(formData).reduce((acc, key) => ({ ...acc, [key]: true }), {}));

        if (!isFormValid()) return;

        setIsSubmitting(true);
        try {
            const response = await authApi.register({
                email: formData.officialEmail,
                phone: `+234${formData.phone}`,
                password: formData.password,
                first_name: formData.firstName,
                last_name: formData.lastName,
                role: 'nafdac_officer',
            });

            setModalConfig({
                type: 'success',
                title: 'Request Submitted',
                message: 'Your regulatory access request has been submitted. You will be notified via your official email.'
            });
            setModalOpen(true);
        } catch (error) {
            const msg = error.message || 'Registration failed. Please try again.';
            setModalConfig({
                type: 'error',
                title: 'Registration Failed',
                message: msg
            });
            setModalOpen(true);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleModalClose = () => {
        setModalOpen(false);
        if (modalConfig.type === 'success') {
            navigate('/nafdac/login');
        }
    };

    return (
        <div className="min-h-screen bg-background p-6">
            <div className="max-w-2xl mx-auto">
                {/* Back Button */}
                <button onClick={() => navigate('/')} className="mb-4">
                    <Icon name="ArrowLeft" size={20} library="fi" className="text-gray-500" />
                </button>

                {/* Header */}
                <div className="text-center mb-8">
                    <div className="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <Icon name="Shield" size={32} library="fi" className="text-primary" />
                    </div>
                    <h1 className="text-2xl font-bold text-accent font-syne">NAFDAC Officer Registration</h1>
                    <p className="text-muted mt-2">Request regulatory access to the SabiLens Enforcement Portal</p>
                </div>

                <Card className="p-8">
                    <form onSubmit={handleSubmit} className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* First Name */}
                            <div>
                                <label className="text-sm font-medium text-accent mb-1 block">First Name</label>
                                <input
                                    type="text"
                                    name="firstName"
                                    value={formData.firstName}
                                    onChange={handleChange}
                                    onBlur={() => handleBlur('firstName')}
                                    className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 ${getFieldError('firstName') ? 'border-danger' : 'border-gray-200'}`}
                                    placeholder="John"
                                />
                                {getFieldError('firstName') && <p className="text-danger text-xs mt-1">{getFieldError('firstName')}</p>}
                            </div>

                            {/* Last Name */}
                            <div>
                                <label className="text-sm font-medium text-accent mb-1 block">Last Name</label>
                                <input
                                    type="text"
                                    name="lastName"
                                    value={formData.lastName}
                                    onChange={handleChange}
                                    onBlur={() => handleBlur('lastName')}
                                    className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 ${getFieldError('lastName') ? 'border-danger' : 'border-gray-200'}`}
                                    placeholder="Doe"
                                />
                                {getFieldError('lastName') && <p className="text-danger text-xs mt-1">{getFieldError('lastName')}</p>}
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* Official Email */}
                            <div>
                                <label className="text-sm font-medium text-accent mb-1 block">Official Email (.gov.ng)</label>
                                <input
                                    type="email"
                                    name="officialEmail"
                                    value={formData.officialEmail}
                                    onChange={handleChange}
                                    onBlur={() => handleBlur('officialEmail')}
                                    className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 ${getFieldError('officialEmail') ? 'border-danger' : 'border-gray-200'}`}
                                    placeholder="j.doe@nafdac.gov.ng"
                                />
                                {getFieldError('officialEmail') && <p className="text-danger text-xs mt-1">{getFieldError('officialEmail')}</p>}
                            </div>

                            {/* Officer ID */}
                            <div>
                                <label className="text-sm font-medium text-accent mb-1 block">Enforcement Officer ID</label>
                                <input
                                    type="text"
                                    name="officerId"
                                    value={formData.officerId}
                                    onChange={handleChange}
                                    onBlur={() => handleBlur('officerId')}
                                    className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 ${getFieldError('officerId') ? 'border-danger' : 'border-gray-200'}`}
                                    placeholder="NFD-123456"
                                />
                                {getFieldError('officerId') && <p className="text-danger text-xs mt-1">{getFieldError('officerId')}</p>}
                            </div>
                        </div>

                        {/* Phone */}
                        <div>
                            <label className="text-sm font-medium text-accent mb-1 block">Phone Number</label>
                            <div className="relative">
                                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 font-medium">+234</span>
                                <input
                                    type="tel"
                                    name="phone"
                                    value={formData.phone}
                                    onChange={handleChange}
                                    onBlur={() => handleBlur('phone')}
                                    placeholder="8012345678"
                                    maxLength="10"
                                    className={`w-full pl-16 pr-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 ${getFieldError('phone') ? 'border-danger' : 'border-gray-200'}`}
                                />
                            </div>
                            {getFieldError('phone') && <p className="text-danger text-xs mt-1">{getFieldError('phone')}</p>}
                        </div>

                        {/* Department */}
                        <div>
                            <label className="text-sm font-medium text-accent mb-1 block">Department / Unit</label>
                            <select
                                name="department"
                                value={formData.department}
                                onChange={handleChange}
                                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20"
                            >
                                <option value="">Select Department</option>
                                <option value="Investigation & Enforcement">Investigation & Enforcement</option>
                                <option value="Post-Marketing Surveillance">Post-Marketing Surveillance</option>
                                <option value="Ports Inspection">Ports Inspection</option>
                                <option value="Laboratory Services">Laboratory Services</option>
                                <option value="FCT / State Coordination">FCT / State Coordination</option>
                            </select>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* Password */}
                            <div>
                                <label className="text-sm font-medium text-accent mb-1 block">Password</label>
                                <input
                                    type="password"
                                    name="password"
                                    value={formData.password}
                                    onChange={handleChange}
                                    onBlur={() => handleBlur('password')}
                                    className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 ${getFieldError('password') ? 'border-danger' : 'border-gray-200'}`}
                                    placeholder="Min. 8 characters"
                                />
                                {getFieldError('password') && <p className="text-danger text-xs mt-1">{getFieldError('password')}</p>}
                            </div>

                            {/* Confirm Password */}
                            <div>
                                <label className="text-sm font-medium text-accent mb-1 block">Confirm Password</label>
                                <input
                                    type="password"
                                    name="confirmPassword"
                                    value={formData.confirmPassword}
                                    onChange={handleChange}
                                    onBlur={() => handleBlur('confirmPassword')}
                                    className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 ${getFieldError('confirmPassword') ? 'border-danger' : 'border-gray-200'}`}
                                    placeholder="Repeat password"
                                />
                                {getFieldError('confirmPassword') && <p className="text-danger text-xs mt-1">{getFieldError('confirmPassword')}</p>}
                            </div>
                        </div>

                        {/* Agreement */}
                        <div className="flex items-start gap-3">
                            <input
                                type="checkbox"
                                name="agreeTerms"
                                id="agreeTerms"
                                checked={formData.agreeTerms}
                                onChange={handleChange}
                                className="mt-1"
                            />
                            <label htmlFor="agreeTerms" className="text-sm text-muted leading-tight">
                                I certify that I am an authorized officer of NAFDAC and agree to the{' '}
                                <button type="button" onClick={() => setShowTermsModal(true)} className="text-primary font-medium hover:underline">Regulatory Access Terms</button>{' '}
                                and{' '}
                                <button type="button" onClick={() => setShowPrivacyModal(true)} className="text-primary font-medium hover:underline">Data Privacy Policy</button>.
                            </label>
                        </div>
                        {getFieldError('agreeTerms') && <p className="text-danger text-xs mt-1">{getFieldError('agreeTerms')}</p>}

                        <Button
                            type="submit"
                            variant="primary"
                            fullWidth
                            size="lg"
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? 'Submitting...' : 'Submit Registration Request'}
                        </Button>

                        <p className="text-center text-sm text-muted">
                            Already have an account?{' '}
                            <Link to="/nafdac/login" className="text-primary font-bold hover:underline">Log in here</Link>
                        </p>
                    </form>
                </Card>
            </div>

            {/* Terms Modal */}
            <Modal isOpen={showTermsModal} onClose={() => setShowTermsModal(false)} type="info" title="Regulatory Access Terms">
                <div className="space-y-4 text-sm text-accent">
                    <p>This portal is for official regulatory and enforcement use only.</p>
                    <p>1. <strong>Confidentiality:</strong> All data accessed through SabiLens is considered high-security and must not be shared outside official channels.</p>
                    <p>2. <strong>Accountability:</strong> You are responsible for all actions taken under your ID.</p>
                    <p>3. <strong>Sovereignty:</strong> NAFDAC retains full control over the final verification of all AI flags.</p>
                </div>
            </Modal>

            {/* Privacy Modal */}
            <Modal isOpen={showPrivacyModal} onClose={() => setShowPrivacyModal(false)} type="info" title="Regulatory Data Privacy">
                <div className="space-y-4 text-sm text-accent">
                    <p>We adhere to the highest standards of data protection (NDPR).</p>
                    <p>1. <strong>Data Encryption:</strong> All communications are protected by end-to-end encryption.</p>
                    <p>2. <strong>Audit Logs:</strong> All officer activity is logged to ensure system integrity.</p>
                </div>
            </Modal>

            {/* Success/Error Modal */}
            <Modal
                isOpen={modalOpen}
                onClose={handleModalClose}
                type={modalConfig.type}
                title={modalConfig.title}
                message={modalConfig.message}
            />
        </div>
    );
};

export default NAFDACSignup;
