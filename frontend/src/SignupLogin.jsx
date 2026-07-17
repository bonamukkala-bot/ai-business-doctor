import { useState } from 'react'
import { useAuth } from './AuthContext.jsx'

const BUSINESS_TYPES = [
  'Retail / Kirana',
  'Restaurant',
  'Pharmacy',
  'Salon / Services',
  'Wholesale',
  'Other',
]

export default function SignupLogin() {
  const { signIn, signUp } = useAuth()
  const [mode, setMode] = useState('login')
  const [shopName, setShopName] = useState('')
  const [businessType, setBusinessType] = useState('Retail')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [loading, setLoading] = useState(false)

  const validate = () => {
    const next = {}

    if (!email.trim()) next.email = 'Email is required.'
    if (!password) next.password = 'Password is required.'
    if (mode === 'signup') {
      if (!shopName.trim()) next.shopName = 'Shop name is required.'
      if (!confirmPassword) next.confirmPassword = 'Please confirm your password.'
      if (password && password.length < 8) next.password = 'Password must be at least 8 characters.'
      if (password && confirmPassword && password !== confirmPassword) {
        next.confirmPassword = 'Passwords do not match.'
      }
    }

    setErrors(next)
    return Object.keys(next).length === 0
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!validate()) return

    setLoading(true)
    setMessage(null)

    const action = mode === 'login' ? signIn : signUp
    const payload = mode === 'login'
      ? { email, password }
      : { email, password, shopName, businessType }
    const { error } = await action(payload)

    if (error) {
      setMessage({ type: 'error', text: error.message || 'Unable to complete your request.' })
    } else {
      setMessage({
        type: 'success',
        text: mode === 'login'
          ? 'Signed in successfully.'
          : 'Account created successfully. Check your email for confirmation.'
      })
      if (mode === 'signup') {
        setShopName('')
        setBusinessType('Retail')
        setEmail('')
        setPassword('')
        setConfirmPassword('')
      }
    }

    setLoading(false)
  }

  const switchMode = (nextMode) => {
    setMode(nextMode)
    setErrors({})
    setMessage(null)
  }

  return (
    <div className="auth-screen">
      <div className="auth-grid-card">
        <div className="auth-card glass-card">
          <div className="auth-brand">
            <div className="brand-mark">AI</div>
            <div>
              <p className="brand-label">AI Business Doctor</p>
              <h1>Your business has a pulse. We help you read it.</h1>
            </div>
          </div>

          <div className="auth-tabs" role="tablist" aria-label="Authentication options">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'signup'}
              className={`auth-tab ${mode === 'signup' ? 'active' : ''}`}
              onClick={() => switchMode('signup')}
            >
              Sign Up
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'login'}
              className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
              onClick={() => switchMode('login')}
            >
              Sign In
            </button>
          </div>

          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            {mode === 'signup' && (
              <>
                <label className="auth-field">
                  <span>Shop Name</span>
                  <input
                    type="text"
                    value={shopName}
                    onChange={(e) => setShopName(e.target.value)}
                    placeholder="e.g. Greenfield Grocers"
                    className={errors.shopName ? 'input-error' : ''}
                  />
                  {errors.shopName && <span className="field-error">{errors.shopName}</span>}
                </label>

                <label className="auth-field">
                  <span>Business Type</span>
                  <select
                    value={businessType}
                    onChange={(e) => setBusinessType(e.target.value)}
                  >
                    {BUSINESS_TYPES.map((type) => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </select>
                </label>
              </>
            )}

            <label className="auth-field">
              <span>Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@business.com"
                className={errors.email ? 'input-error' : ''}
              />
              {errors.email && <span className="field-error">{errors.email}</span>}
            </label>

            <label className="auth-field">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                className={errors.password ? 'input-error' : ''}
              />
              {errors.password && <span className="field-error">{errors.password}</span>}
            </label>

            {mode === 'signup' && (
              <label className="auth-field">
                <span>Confirm Password</span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat your password"
                  className={errors.confirmPassword ? 'input-error' : ''}
                />
                {errors.confirmPassword && <span className="field-error">{errors.confirmPassword}</span>}
              </label>
            )}

            {message && (
              <div className={`auth-banner ${message.type}`}>
                {message.text}
              </div>
            )}

            <button className="auth-submit" type="submit" disabled={loading}>
              {loading ? <span className="button-spinner" aria-hidden="true" /> : null}
              {loading ? 'Working…' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        </div>

        <div className="auth-visual">
          <div className="pulse-blob" />
          <div className="pulse-ring" />
        </div>
      </div>
    </div>
  )
}
