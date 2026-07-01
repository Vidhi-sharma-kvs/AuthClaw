import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../components/Common/Toast';
import apiClient from '../../services/api';
import { 
  ShieldAlert, 
  Lock, 
  Mail, 
  User, 
  ArrowRight, 
  ShieldCheck, 
  KeyRound, 
  RefreshCw, 
  Globe, 
  Building2, 
  Copy, 
  Check, 
  Info 
} from 'lucide-react';

const Login = () => {
  const { user, login, verifyOtp, mfaSessionId, clearMfaSession, isAuthenticated } = useAuth();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();

  // Redirect on successful authentication
  useEffect(() => {
    if (isAuthenticated) {
      const fallback = user?.role === 'Platform Admin' ? '/platform/dashboard' : '/chat';
      const from = location.state?.from?.pathname || fallback;
      const safeFrom = user?.role === 'Platform Admin' && !from.startsWith('/platform') ? fallback : from;
      navigate(safeFrom, { replace: true });
    }
  }, [isAuthenticated, user, navigate, location]);

  // Step state: 'login' | 'register' | 'verify_email' | 'verify_domain' | 'otp' | MFA reset steps
  const [step, setStep] = useState('login');
  
  // Login Credentials
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  
  // Registration credentials
  const [regName, setRegName] = useState('');
  const [regFullName, setRegFullName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regDomain, setRegDomain] = useState('');

  // Verification states
  const [emailToVerify, setEmailToVerify] = useState('');
  const [emailToken, setEmailToken] = useState('');
  const [domainToVerify, setDomainToVerify] = useState('');
  const [domainToken, setDomainToken] = useState('');
  const [copied, setCopied] = useState(false);
  
  // OTP
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [otpTimer, setOtpTimer] = useState(60);
  const [mfaResetEmail, setMfaResetEmail] = useState('');
  const [mfaResetPassword, setMfaResetPassword] = useState('');
  const [mfaResetToken, setMfaResetToken] = useState('');
  const [passwordResetEmail, setPasswordResetEmail] = useState('');
  const [passwordResetToken, setPasswordResetToken] = useState('');
  const [passwordResetNew, setPasswordResetNew] = useState('');
  const [passwordResetConfirm, setPasswordResetConfirm] = useState('');
  
  // UI states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [totpSecret, setTotpSecret] = useState('');
  const [otpauthUri, setOtpauthUri] = useState('');
  // Transition helper when MFA is required
  useEffect(() => {
    if (mfaSessionId) {
      setStep('otp');
      setOtpTimer(60);
      setError(null);
    } else if (step === 'otp') {
      setStep('login');
    }
  }, [mfaSessionId]);

  // OTP Countdown timer
  useEffect(() => {
    let timer;
    if (step === 'otp' && otpTimer > 0) {
      timer = setInterval(() => {
        setOtpTimer((prev) => prev - 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [step, otpTimer]);

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Please fill in all credentials.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await login(username.trim(), password);
      if (result.mfaRequired) {
        addToast('MFA verification required. Please enter the OTP code from your authenticator app.', 'info');
      }
    } catch (err) {
      if (err.data) {
        if (err.data.email_verified === false) {
          setEmailToVerify(err.data.email);
          if (err.data.email_token) setEmailToken(err.data.email_token);
          if (err.data.domain) setDomainToVerify(err.data.domain);
          if (err.data.domain_token) setDomainToken(err.data.domain_token);
          setStep('verify_email');
          setError('Email is not verified. Please verify your email.');
          return;
        }
        if (err.data.domain_verified === false) {
          setDomainToVerify(err.data.domain);
          setDomainToken(err.data.domain_token);
          setEmailToVerify(username.trim());
          setStep('verify_domain');
          setError('Domain is not verified. Please verify domain ownership.');
          return;
        }
      }
      setError(err.message || 'Incorrect username or password.');
      addToast(err.message || 'Login failed.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    if (!regName.trim() || !regFullName.trim() || !regEmail.trim() || !regPassword.trim() || !regDomain.trim()) {
      setError('Please fill in all registration fields.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.post('/auth/register', {
        name: regName.trim(),
        full_name: regFullName.trim(),
        email: regEmail.trim(),
        password: regPassword,
        domain: regDomain.trim()
      });
      addToast('Registration received. Check your work email for the verification token.', 'success');
      setEmailToVerify(regEmail.trim());
      setDomainToVerify(regDomain.trim());
      setDomainToken(response.data.domain_token);
      setEmailToken(response.data.email_token || '');
      setTotpSecret(response.data.totp_secret || '');
      setOtpauthUri(response.data.otpauth_uri || '');
      setStep('mfa_enroll');
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed.');
      addToast(err.response?.data?.detail || 'Registration failed.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyEmailSubmit = async (e) => {
    e.preventDefault();
    if (!emailToken.trim()) {
      setError('Please enter the verification token.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.post('/auth/verify-email', { token: emailToken.trim() });
      if (response.data?.activated) {
        addToast(response.data.message || 'Email verified. Tenant workspace activated.', 'success');
        setStep('login');
        setUsername(emailToVerify || regEmail);
        setPassword('');
        return;
      }
      addToast('Email verified successfully! Proceed to domain verification.', 'success');
      setStep('verify_domain');
    } catch (err) {
      setError(err.response?.data?.detail || 'Email verification failed.');
      addToast(err.response?.data?.detail || 'Email verification failed.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyDomainSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await apiClient.post('/auth/verify-domain', {
        domain: domainToVerify,
        token: domainToken
      });
      addToast('Domain verified successfully! You can now log in.', 'success');
      setStep('login');
      setUsername(emailToVerify || regEmail);
      setPassword('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Domain verification failed.');
      addToast(err.response?.data?.detail || 'Domain verification failed.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleOtpChange = (index, value) => {
    if (isNaN(value)) return;
    
    const newOtp = [...otp];
    newOtp[index] = value.substring(value.length - 1);
    setOtp(newOtp);

    if (value && index < 5) {
      const nextInput = document.getElementById(`otp-${index + 1}`);
      if (nextInput) nextInput.focus();
    }
  };

  const handleKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      const prevInput = document.getElementById(`otp-${index - 1}`);
      if (prevInput) {
        prevInput.focus();
        const newOtp = [...otp];
        newOtp[index - 1] = '';
        setOtp(newOtp);
      }
    }
  };

  const handleOtpSubmit = async (e) => {
    e.preventDefault();
    const code = otp.join('');
    if (code.length !== 6) {
      setError('Please enter the complete 6-digit verification code.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await verifyOtp(code);
      addToast('Authenticated successfully. Welcome to AuthClaw Console.', 'success');
    } catch (err) {
      setError(err.message || 'Invalid verification token.');
      addToast(err.message || 'OTP verification failed.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = () => {
    if (otpTimer > 0) return;
    setOtpTimer(60);
    setOtp(['', '', '', '', '', '']);
    document.getElementById('otp-0')?.focus();
    setError(null);
    addToast('A new OTP token has been generated. Please check your authenticator app.', 'info');
  };

  const startMfaReset = () => {
    setMfaResetEmail(username.trim());
    setMfaResetPassword(password);
    setMfaResetToken('');
    setError(null);
    setStep('mfa_reset_request');
  };

  const handleMfaResetRequest = async (e) => {
    e.preventDefault();
    if (!mfaResetEmail.trim() || !mfaResetPassword.trim()) {
      setError('Enter your email and password to request an MFA reset.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.post('/auth/mfa/reset-request', {
        username: mfaResetEmail.trim(),
        password: mfaResetPassword
      });
      setMfaResetToken(response.data.reset_token || '');
      addToast(response.data.message || 'MFA reset token sent to your email.', 'success');
      setStep('mfa_reset_confirm');
    } catch (err) {
      setError(err.response?.data?.detail || 'MFA reset request failed.');
      addToast(err.response?.data?.detail || 'MFA reset request failed.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleMfaResetConfirm = async (e) => {
    e.preventDefault();
    if (!mfaResetToken.trim()) {
      setError('Enter the MFA reset token from your email.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.post('/auth/mfa/reset-confirm', {
        token: mfaResetToken.trim()
      });
      setTotpSecret(response.data.totp_secret || '');
      setOtpauthUri(response.data.otpauth_uri || '');
      setOtp(['', '', '', '', '', '']);
      addToast(response.data.message || 'MFA setup key rotated.', 'success');
      setStep('mfa_reset_enroll');
    } catch (err) {
      setError(err.response?.data?.detail || 'MFA reset confirmation failed.');
      addToast(err.response?.data?.detail || 'MFA reset confirmation failed.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const finishMfaReset = () => {
    clearMfaSession();
    setPassword('');
    setMfaResetPassword('');
    setMfaResetToken('');
    setOtp(['', '', '', '', '', '']);
    setStep('login');
    setError(null);
    setUsername(mfaResetEmail || username);
    addToast('MFA reset complete. Sign in with your new authenticator code.', 'info');
  };

  const handleForgotPassword = (e) => {
    e.preventDefault();
    setPasswordResetEmail(username.trim());
    setPasswordResetToken('');
    setPasswordResetNew('');
    setPasswordResetConfirm('');
    setError(null);
    setStep('password_reset_request');
  };

  const handlePasswordResetRequest = async (e) => {
    e.preventDefault();
    if (!passwordResetEmail.trim()) {
      setError('Enter your account email to request a password reset.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.post('/auth/password/reset-request', {
        username: passwordResetEmail.trim()
      });
      const resetToken = response.data.reset_token || '';
      setPasswordResetToken(resetToken);
      addToast(response.data.message || 'Password reset token sent if the account exists.', 'success');
      if (response.data.email_error) {
        addToast(response.data.email_error, 'info');
      }
      if (response.data.local_debug) {
        setError(response.data.local_debug);
        addToast(response.data.local_debug, 'info');
      }
      if (resetToken) {
        setStep('password_reset_confirm');
      } else if (!response.data.local_debug) {
        setStep('login');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Password reset request failed.');
      addToast(err.response?.data?.detail || 'Password reset request failed.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordResetConfirm = async (e) => {
    e.preventDefault();
    if (!passwordResetToken.trim()) {
      setError('Enter the password reset token from your email.');
      return;
    }
    if (!passwordResetNew || passwordResetNew.length < 8) {
      setError('New password must be at least 8 characters.');
      return;
    }
    if (passwordResetNew !== passwordResetConfirm) {
      setError('New password and confirmation do not match.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.post('/auth/password/reset-confirm', {
        token: passwordResetToken.trim(),
        password: passwordResetNew
      });
      setUsername(response.data.email || passwordResetEmail);
      setPassword('');
      setPasswordResetToken('');
      setPasswordResetNew('');
      setPasswordResetConfirm('');
      setStep('login');
      addToast(response.data.message || 'Password reset complete. Sign in with the new password.', 'success');
    } catch (err) {
      setError(err.response?.data?.detail || 'Password reset confirmation failed.');
      addToast(err.response?.data?.detail || 'Password reset confirmation failed.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const goBackToLogin = () => {
    clearMfaSession();
    setStep('login');
    setError(null);
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(domainToken);
    setCopied(true);
    addToast('Verification token copied to clipboard!', 'success');
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4 relative overflow-hidden">
      {/* Background gradients */}
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-[350px] h-[350px] bg-violet-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-[350px] h-[350px] bg-fuchsia-600/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Core card */}
      <div className="w-full max-w-[460px] glass-card p-8 space-y-6 border border-white/10 shadow-2xl relative z-10 select-none">
        
        {/* Logo Section */}
        <div className="flex flex-col items-center text-center space-y-2">
          <div className="p-3 bg-gradient-to-tr from-violet-600 to-fuchsia-600 rounded-xl shadow-xl shadow-violet-500/20">
            <ShieldAlert className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-white via-gray-200 to-gray-400 bg-clip-text text-transparent tracking-tight">
            AuthClaw Console
          </h1>
          <p className="text-xs text-gray-500 max-w-[320px]">
            Enterprise AI Security Gateway and Governance Platform
          </p>
        </div>

        {/* Tab switcher for Sign In / Register (only in login/register steps) */}
        {(step === 'login' || step === 'register') && (
          <div className="flex bg-slate-900/60 p-1 rounded-lg border border-white/5">
            <button
              onClick={() => { setStep('login'); setError(null); }}
              className={`flex-1 py-2 text-xs font-semibold rounded-md transition-all ${
                step === 'login' 
                  ? 'bg-violet-600 text-white shadow-sm' 
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => { setStep('register'); setError(null); }}
              className={`flex-1 py-2 text-xs font-semibold rounded-md transition-all ${
                step === 'register' 
                  ? 'bg-violet-600 text-white shadow-sm' 
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Register Tenant
            </button>
          </div>
        )}

        {/* Errors Box */}
        {error && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400 text-xs leading-relaxed animate-fadeIn">
            {error}
          </div>
        )}

        {/* Step: Login credentials */}
        {step === 'login' && (
          <form onSubmit={handleLoginSubmit} className="space-y-4">
            <div className="space-y-3">
              {/* Username */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1">Security Username or Email</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                    <Mail className="w-4 h-4" />
                  </div>
                  <input
                    type="text"
                    required
                    placeholder="e.g. admin@organization.com"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors placeholder-gray-600"
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="block text-xs font-semibold text-gray-400">Security Passcode</label>
                  <a 
                    href="#forgot" 
                    onClick={handleForgotPassword}
                    className="text-[11px] font-semibold text-violet-400 hover:text-violet-300 transition-colors"
                  >
                    Forgot Password?
                  </a>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type="password"
                    required
                    placeholder="••••••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors placeholder-gray-600"
                  />
                </div>
              </div>
            </div>

            {/* Remember Me */}
            <div className="flex items-center justify-between text-xs select-none pt-1">
              <label className="flex items-center gap-2 text-gray-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="rounded border-white/10 bg-slate-900 text-violet-600 focus:ring-0 focus:ring-offset-0 cursor-pointer"
                />
                Remember this workstation
              </label>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-95 shadow-lg shadow-violet-500/10 transition-all disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Authenticating...
                </>
              ) : (
                <>
                  Sign In to Console <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>

          </form>
        )}

        {/* Step: Register Tenant */}
        {step === 'register' && (
          <form onSubmit={handleRegisterSubmit} className="space-y-4">
            <div className="space-y-3">
              {/* Organization Name */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1">Organization Name</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                    <Building2 className="w-4 h-4" />
                  </div>
                  <input
                    type="text"
                    required
                    placeholder="e.g. TrueFirms Inc."
                    value={regName}
                    onChange={(e) => setRegName(e.target.value)}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors placeholder-gray-600"
                  />
                </div>
              </div>

              {/* Email */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1">Full Name</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                    <User className="w-4 h-4" />
                  </div>
                  <input
                    type="text"
                    required
                    placeholder="Your full name"
                    value={regFullName}
                    onChange={(e) => setRegFullName(e.target.value)}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors placeholder-gray-600"
                  />
                </div>
              </div>

              {/* Email */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1">Administrator Email</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                    <Mail className="w-4 h-4" />
                  </div>
                  <input
                    type="email"
                    required
                    placeholder="admin@organization.com"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors placeholder-gray-600"
                  />
                </div>
                <p className="mt-1.5 text-[10px] text-violet-300">
                  This first verified user becomes the Tenant Super Admin. Additional roles are assigned later in Settings.
                </p>
              </div>

              {/* Domain */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1">Company Domain</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                    <Globe className="w-4 h-4" />
                  </div>
                  <input
                    type="text"
                    required
                    placeholder="organization.com"
                    value={regDomain}
                    onChange={(e) => setRegDomain(e.target.value)}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors placeholder-gray-600"
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1">Access Passcode</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type="password"
                    required
                    placeholder="••••••••••••"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors placeholder-gray-600"
                  />
                </div>
              </div>
            </div>

            {/* Disclaimer */}
            <div className="p-3 bg-violet-950/20 border border-violet-500/10 rounded-lg flex items-start gap-2.5">
              <Info className="w-4 h-4 text-violet-400 shrink-0 mt-0.5" />
              <p className="text-[10px] text-gray-400 leading-normal">
                <strong>Key Security Notice:</strong> Registration activates only after email and domain verification. The registering administrator receives Super Admin access for this tenant; provider secrets are encrypted and never exposed across tenants.
              </p>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-95 shadow-lg shadow-violet-500/10 transition-all disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Provisioning Tenant...
                </>
              ) : (
                <>
                  Register Organization <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        )}

        {/* Step: MFA Enrollment */}
        {step === 'mfa_enroll' && (
          <div className="space-y-5 animate-scaleUp">
            <div className="space-y-2 text-center">
              <div className="flex justify-center text-violet-400 mb-1">
                <ShieldAlert className="w-8 h-8" />
              </div>
              <h3 className="text-sm font-bold text-white">MFA Enrollment (Security Configuration)</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed">
                Scan the QR link or manually enter the secret key in your authenticator app (e.g. Google Authenticator, Authy).
              </p>
            </div>

            <div className="space-y-3 bg-slate-900/80 p-3.5 rounded-lg border border-white/10">
              <div>
                <label className="block text-[10px] uppercase font-bold text-gray-500 mb-1">Base32 Secret Key</label>
                <div className="flex items-center justify-between gap-2 bg-slate-950 p-2.5 rounded border border-white/5 font-mono text-xs text-violet-400 select-all overflow-x-auto">
                  <span className="whitespace-nowrap break-all">{totpSecret}</span>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(totpSecret);
                      addToast('Secret Key copied to clipboard!', 'success');
                    }}
                    className="text-gray-400 hover:text-white shrink-0"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-gray-500 mb-1">OTPAuth URI (QR Link)</label>
                <div className="flex items-center justify-between gap-2 bg-slate-950 p-2.5 rounded border border-white/5 font-mono text-[10px] text-gray-400 select-all overflow-x-auto">
                  <span className="truncate max-w-[220px]">{otpauthUri}</span>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(otpauthUri);
                      addToast('OTPAuth URI copied to clipboard!', 'success');
                    }}
                    className="text-gray-400 hover:text-white shrink-0"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>

            <div className="p-3 bg-slate-900/40 border border-white/5 rounded-lg flex items-start gap-2.5">
              <Info className="w-4 h-4 text-gray-400 shrink-0 mt-0.5" />
              <p className="text-[10px] text-gray-500 leading-normal">
                IMPORTANT: This secret key is shown ONLY once. Ensure you save it securely now before proceeding.
              </p>
            </div>

            <button
              type="button"
              onClick={() => setStep('verify_email')}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-95 shadow-lg shadow-violet-500/10 transition-all"
            >
              I have saved the key, proceed to verify email
            </button>
          </div>
        )}

        {/* Step: Email Verification */}
        {step === 'verify_email' && (
          <form onSubmit={handleVerifyEmailSubmit} className="space-y-5 animate-scaleUp">
            <div className="space-y-2 text-center">
              <div className="flex justify-center text-violet-400 mb-1">
                <Mail className="w-8 h-8 animate-pulse" />
              </div>
              <h3 className="text-sm font-bold text-white">Email Verification Required</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed px-2">
                We sent a verification token to <strong className="text-violet-400">{emailToVerify}</strong>. Enter the token from that email below.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1">Verification Token</label>
              <input
                type="text"
                required
                placeholder="Paste email token here..."
                value={emailToken}
                onChange={(e) => setEmailToken(e.target.value)}
                className="w-full bg-slate-900 border border-white/10 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors text-center font-mono placeholder-gray-600"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-95 shadow-lg shadow-violet-500/10 transition-all disabled:opacity-50"
            >
              {loading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                'Confirm Email'
              )}
            </button>

            <div className="text-center">
              <button
                type="button"
                onClick={goBackToLogin}
                className="text-xs text-gray-500 hover:text-white transition-colors"
              >
                ← Return to Sign In
              </button>
            </div>
          </form>
        )}

        {/* Step: Domain Verification */}
        {step === 'verify_domain' && (
          <form onSubmit={handleVerifyDomainSubmit} className="space-y-5 animate-scaleUp">
            <div className="space-y-2 text-center">
              <div className="flex justify-center text-violet-400 mb-1">
                <Globe className="w-8 h-8" />
              </div>
              <h3 className="text-sm font-bold text-white">Domain Ownership Verification</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed">
                Configure the following TXT record on your DNS zone for domain <strong className="text-violet-400">{domainToVerify}</strong>:
              </p>
            </div>

            <div className="space-y-3 bg-slate-900/80 p-3.5 rounded-lg border border-white/10">
              <div className="flex justify-between items-center text-[10px] text-gray-500 font-semibold uppercase tracking-wider">
                <span>Record Type / Name</span>
                <span>TXT / @</span>
              </div>
              <div className="flex items-center justify-between gap-2 bg-slate-950 p-2.5 rounded border border-white/5 font-mono text-xs text-violet-400 select-all overflow-x-auto">
                <span className="whitespace-nowrap break-all">{domainToken}</span>
                <button
                  type="button"
                  onClick={copyToClipboard}
                  className="text-gray-400 hover:text-white shrink-0"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            <div className="p-3 bg-slate-900/40 border border-white/5 rounded-lg flex items-start gap-2.5">
              <Info className="w-4 h-4 text-gray-400 shrink-0 mt-0.5" />
              <p className="text-[10px] text-gray-500 leading-normal">
                Our DNS resolver queries standard root servers. Propagation can take several minutes. Ensure record points strictly to the token value.
              </p>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-95 shadow-lg shadow-violet-500/10 transition-all disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Verifying DNS Record...
                </>
              ) : (
                'Verify Domain Ownership'
              )}
            </button>

            <div className="text-center">
              <button
                type="button"
                onClick={goBackToLogin}
                className="text-xs text-gray-500 hover:text-white transition-colors"
              >
                ← Return to Sign In
              </button>
            </div>
          </form>
        )}

        {/* Step: OTP / MFA */}
        {step === 'otp' && (
          <form onSubmit={handleOtpSubmit} className="space-y-6 animate-scaleUp">
            <div className="space-y-3 text-center">
              <div className="flex justify-center text-violet-400 mb-1">
                <KeyRound className="w-8 h-8" />
              </div>
              <h3 className="text-sm font-bold text-white">MFA Multi-Factor Verification</h3>
              <p className="text-[11px] text-gray-500 leading-relaxed px-4">
                Workstation requires multi-factor clearance. Enter the 6-digit code from your authenticator app.
              </p>
            </div>

            {/* Code inputs */}
            <div className="flex justify-center gap-2.5">
              {otp.map((digit, i) => (
                <input
                  key={i}
                  id={`otp-${i}`}
                  type="text"
                  maxLength={1}
                  required
                  value={digit}
                  onChange={(e) => handleOtpChange(i, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(i, e)}
                  className="w-12 h-12 bg-slate-900 border border-white/10 rounded-lg text-center text-lg font-bold text-white focus:outline-none focus:border-violet-500 transition-colors"
                />
              ))}
            </div>

            {/* Action buttons */}
            <div className="space-y-3">
              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-95 shadow-lg shadow-violet-500/10 transition-all disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" /> Verifying Code...
                  </>
                ) : (
                  <>
                    Verify Cleared State <ShieldCheck className="w-4 h-4" />
                  </>
                )}
              </button>

              <div className="flex justify-between items-center text-xs text-gray-500 px-1">
                <button
                  type="button"
                  onClick={goBackToLogin}
                  className="hover:text-white transition-colors"
                >
                  ← Change credentials
                </button>
                
                <button
                  type="button"
                  onClick={startMfaReset}
                  className="font-semibold text-violet-400 hover:text-violet-300 transition-colors"
                >
                  Lost authenticator?
                </button>
              </div>
            </div>
          </form>
        )}

        {/* Step: Password reset request */}
        {step === 'password_reset_request' && (
          <form onSubmit={handlePasswordResetRequest} className="space-y-5 animate-scaleUp">
            <div className="space-y-2 text-center">
              <div className="flex justify-center text-violet-400 mb-1">
                <KeyRound className="w-8 h-8" />
              </div>
              <h3 className="text-sm font-bold text-white">Reset Password</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed px-2">
                Enter your verified account email. AuthClaw will send a one-time password reset token.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1">Account Email</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  type="email"
                  required
                  value={passwordResetEmail}
                  onChange={(e) => setPasswordResetEmail(e.target.value)}
                  className="w-full bg-slate-900 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors placeholder-gray-600"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-95 shadow-lg shadow-violet-500/10 transition-all disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Sending Reset Token...
                </>
              ) : (
                'Send Password Reset Token'
              )}
            </button>

            <div className="text-center">
              <button
                type="button"
                onClick={goBackToLogin}
                className="text-xs text-gray-500 hover:text-white transition-colors"
              >
                Back to sign in
              </button>
            </div>
          </form>
        )}

        {/* Step: Password reset confirmation */}
        {step === 'password_reset_confirm' && (
          <form onSubmit={handlePasswordResetConfirm} className="space-y-5 animate-scaleUp">
            <div className="space-y-2 text-center">
              <div className="flex justify-center text-violet-400 mb-1">
                <Mail className="w-8 h-8 animate-pulse" />
              </div>
              <h3 className="text-sm font-bold text-white">Create New Password</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed px-2">
                Enter the reset token sent to <strong className="text-violet-400">{passwordResetEmail}</strong>, then create a new password.
              </p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1">Reset Token</label>
                <input
                  type="text"
                  required
                  placeholder="Paste reset token here..."
                  value={passwordResetToken}
                  onChange={(e) => setPasswordResetToken(e.target.value)}
                  className="w-full bg-slate-900 border border-white/10 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors text-center font-mono placeholder-gray-600"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1">New Password</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type="password"
                    required
                    value={passwordResetNew}
                    onChange={(e) => setPasswordResetNew(e.target.value)}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors placeholder-gray-600"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1">Confirm New Password</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type="password"
                    required
                    value={passwordResetConfirm}
                    onChange={(e) => setPasswordResetConfirm(e.target.value)}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors placeholder-gray-600"
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-95 shadow-lg shadow-violet-500/10 transition-all disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Updating Password...
                </>
              ) : (
                'Reset Password'
              )}
            </button>

            <div className="text-center">
              <button
                type="button"
                onClick={goBackToLogin}
                className="text-xs text-gray-500 hover:text-white transition-colors"
              >
                Back to sign in
              </button>
            </div>
          </form>
        )}

        {/* Step: MFA reset request */}
        {step === 'mfa_reset_request' && (
          <form onSubmit={handleMfaResetRequest} className="space-y-5 animate-scaleUp">
            <div className="space-y-2 text-center">
              <div className="flex justify-center text-violet-400 mb-1">
                <KeyRound className="w-8 h-8" />
              </div>
              <h3 className="text-sm font-bold text-white">Reset Authenticator</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed px-2">
                Confirm your email and password. AuthClaw will send a one-time MFA reset token to your verified email address.
              </p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1">Account Email</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                    <Mail className="w-4 h-4" />
                  </div>
                  <input
                    type="email"
                    required
                    value={mfaResetEmail}
                    onChange={(e) => setMfaResetEmail(e.target.value)}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors placeholder-gray-600"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1">Security Passcode</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type="password"
                    required
                    value={mfaResetPassword}
                    onChange={(e) => setMfaResetPassword(e.target.value)}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors placeholder-gray-600"
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-95 shadow-lg shadow-violet-500/10 transition-all disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Sending Reset Token...
                </>
              ) : (
                'Send MFA Reset Token'
              )}
            </button>

            <div className="text-center">
              <button
                type="button"
                onClick={goBackToLogin}
                className="text-xs text-gray-500 hover:text-white transition-colors"
              >
                Back to sign in
              </button>
            </div>
          </form>
        )}

        {/* Step: MFA reset token confirmation */}
        {step === 'mfa_reset_confirm' && (
          <form onSubmit={handleMfaResetConfirm} className="space-y-5 animate-scaleUp">
            <div className="space-y-2 text-center">
              <div className="flex justify-center text-violet-400 mb-1">
                <Mail className="w-8 h-8 animate-pulse" />
              </div>
              <h3 className="text-sm font-bold text-white">Confirm MFA Reset</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed px-2">
                Enter the reset token sent to <strong className="text-violet-400">{mfaResetEmail}</strong>. A new authenticator setup key will be generated after confirmation.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1">MFA Reset Token</label>
              <input
                type="text"
                required
                placeholder="Paste reset token here..."
                value={mfaResetToken}
                onChange={(e) => setMfaResetToken(e.target.value)}
                className="w-full bg-slate-900 border border-white/10 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors text-center font-mono placeholder-gray-600"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-95 shadow-lg shadow-violet-500/10 transition-all disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Rotating MFA Key...
                </>
              ) : (
                'Generate New Setup Key'
              )}
            </button>

            <div className="text-center">
              <button
                type="button"
                onClick={goBackToLogin}
                className="text-xs text-gray-500 hover:text-white transition-colors"
              >
                Back to sign in
              </button>
            </div>
          </form>
        )}

        {/* Step: MFA reset enrollment */}
        {step === 'mfa_reset_enroll' && (
          <div className="space-y-5 animate-scaleUp">
            <div className="space-y-2 text-center">
              <div className="flex justify-center text-violet-400 mb-1">
                <ShieldAlert className="w-8 h-8" />
              </div>
              <h3 className="text-sm font-bold text-white">New MFA Setup Key</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed">
                Add this new setup key to your authenticator app. Your old MFA codes will no longer work.
              </p>
            </div>

            <div className="space-y-3 bg-slate-900/80 p-3.5 rounded-lg border border-white/10">
              <div>
                <label className="block text-[10px] uppercase font-bold text-gray-500 mb-1">Base32 Secret Key</label>
                <div className="flex items-center justify-between gap-2 bg-slate-950 p-2.5 rounded border border-white/5 font-mono text-xs text-violet-400 select-all overflow-x-auto">
                  <span className="whitespace-nowrap break-all">{totpSecret}</span>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(totpSecret);
                      addToast('Secret Key copied to clipboard!', 'success');
                    }}
                    className="text-gray-400 hover:text-white shrink-0"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-gray-500 mb-1">OTPAuth URI</label>
                <div className="flex items-center justify-between gap-2 bg-slate-950 p-2.5 rounded border border-white/5 font-mono text-[10px] text-gray-400 select-all overflow-x-auto">
                  <span className="truncate max-w-[220px]">{otpauthUri}</span>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(otpauthUri);
                      addToast('OTPAuth URI copied to clipboard!', 'success');
                    }}
                    className="text-gray-400 hover:text-white shrink-0"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>

            <div className="p-3 bg-slate-900/40 border border-white/5 rounded-lg flex items-start gap-2.5">
              <Info className="w-4 h-4 text-gray-400 shrink-0 mt-0.5" />
              <p className="text-[10px] text-gray-500 leading-normal">
                Save this key in your authenticator app now. AuthClaw will only verify the 6-digit code generated by that app.
              </p>
            </div>

            <button
              type="button"
              onClick={finishMfaReset}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-95 shadow-lg shadow-violet-500/10 transition-all"
            >
              I added the key, return to sign in
            </button>
          </div>
        )}

        {/* Security Footer Notice */}
        <div className="text-[10px] text-center text-gray-600 flex items-center justify-center gap-1.5 border-t border-white/5 pt-4">
          <Lock className="w-3.5 h-3.5" /> FIPS 140-2 Encrypted Session Established
        </div>
      </div>
    </div>
  );
};

export default Login;
