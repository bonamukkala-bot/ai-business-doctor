import { useState, useEffect } from 'react'
import axios from 'axios'
import { API_BASE_URL } from '../config'

const BUSINESS_GOAL_OPTIONS = [
  { value: 'increase_profit', label: 'Increase Profit' },
  { value: 'increase_revenue', label: 'Increase Revenue' },
  { value: 'reduce_inventory', label: 'Reduce Inventory' },
  { value: 'improve_cash_flow', label: 'Improve Cash Flow' },
  { value: 'reduce_waste', label: 'Reduce Waste' },
  { value: 'prepare_expansion', label: 'Prepare for Expansion' },
  { value: 'open_branch', label: 'Open New Branch' }
]

export default function SettingsPage({ dataStatus, showUploadForm, connectionType, liveSalesPath, liveInventoryPath, salesFile, inventoryFile, uploading, uploadError, uploadSuccess, handleUpload, handleConnectLive, handleDisconnectLive, handleResetDemo, setShowUploadForm, setConnectionType, setLiveSalesPath, setLiveInventoryPath, setSalesFile, setInventoryFile, signOut, user }) {
  const [phoneNumber, setPhoneNumber] = useState('')
  const [phoneSaving, setPhoneSaving] = useState(false)
  const [phoneError, setPhoneError] = useState(null)
  const [phoneSuccess, setPhoneSuccess] = useState(null)
  const [businessGoal, setBusinessGoal] = useState('')
  const [businessGoalSaving, setBusinessGoalSaving] = useState(false)
  const [businessGoalError, setBusinessGoalError] = useState(null)
  const [businessGoalSuccess, setBusinessGoalSuccess] = useState(null)

  // Fetch business goal on mount
  useEffect(() => {
    const fetchBusinessGoal = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/business-goal`)
        if (response.data.business_goal) {
          setBusinessGoal(response.data.business_goal)
        }
      } catch (error) {
        console.error('Failed to fetch business goal:', error)
      }
    }
    fetchBusinessGoal()
  }, [])

  const handleUpdatePhone = async () => {
    if (!phoneNumber.trim()) {
      setPhoneError('Please enter a phone number')
      return
    }

    setPhoneSaving(true)
    setPhoneError(null)
    setPhoneSuccess(null)

    try {
      await axios.post(`${API_BASE_URL}/api/user/update-phone`, {
        phone_number: phoneNumber.trim()
      })
      setPhoneSuccess('Phone number updated successfully!')
      setPhoneNumber('')
    } catch (error) {
      setPhoneError(error.response?.data?.detail || 'Failed to update phone number')
    } finally {
      setPhoneSaving(false)
    }
  }

  const handleUpdateBusinessGoal = async (goalValue) => {
    setBusinessGoalSaving(true)
    setBusinessGoalError(null)
    setBusinessGoalSuccess(null)

    try {
      await axios.post(`${API_BASE_URL}/api/business-goal`, {
        business_goal: goalValue
      })
      setBusinessGoal(goalValue)
      setBusinessGoalSuccess('Business goal updated successfully!')
    } catch (error) {
      setBusinessGoalError(error.response?.data?.detail || 'Failed to update business goal')
    } finally {
      setBusinessGoalSaving(false)
    }
  }

  const handleSendWhatsApp = async () => {
    try {
      await axios.post(`${API_BASE_URL}/api/alerts/send-whatsapp`, {
        user_id: user.id
      })
      alert('WhatsApp alert sent successfully!')
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to send WhatsApp alert')
    }
  }

  return (
    <div className="settings-page">
      <section className="data-source-card card-interactive">
        <div className="section-head">
          <span className="section-eyebrow">Settings</span>
          <h2 className="section-title">Data Connection</h2>
        </div>
        <div className="settings-placeholder">Data connection management placeholder</div>
      </section>

      <section className="business-goal-card card-interactive">
        <div className="section-head">
          <span className="section-eyebrow">Preferences</span>
          <h2 className="section-title">Business Goal</h2>
        </div>
        <div className="business-goal-settings">
          <p className="business-goal-description">
            Select your primary business goal to tailor AI recommendations to your priorities.
          </p>
          <div className="business-goal-selector">
            {BUSINESS_GOAL_OPTIONS.map((option) => (
              <button
                key={option.value}
                className={`goal-option ${businessGoal === option.value ? 'active' : ''} ${businessGoalSaving ? 'disabled' : ''}`}
                onClick={() => handleUpdateBusinessGoal(option.value)}
                disabled={businessGoalSaving}
              >
                {option.label}
              </button>
            ))}
          </div>
          {!businessGoal && (
            <p className="business-goal-prompt">Please select a business goal to get started.</p>
          )}
          {businessGoalError && <p className="business-goal-error">{businessGoalError}</p>}
          {businessGoalSuccess && <p className="business-goal-success">{businessGoalSuccess}</p>}
        </div>
      </section>

      <section className="whatsapp-card card-interactive">
        <div className="section-head">
          <span className="section-eyebrow">Notifications</span>
          <h2 className="section-title">WhatsApp Alerts</h2>
        </div>
        <div className="whatsapp-settings">
          <div className="phone-input-group">
            <label htmlFor="phone">Phone Number (with country code, e.g., +919876543210)</label>
            <input
              id="phone"
              type="tel"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              placeholder="+91XXXXXXXXXX"
              className="phone-input"
            />
            <button 
              className="btn-primary" 
              onClick={handleUpdatePhone}
              disabled={phoneSaving}
            >
              {phoneSaving ? 'Saving...' : 'Save Phone Number'}
            </button>
          </div>
          {phoneError && <p className="phone-error">{phoneError}</p>}
          {phoneSuccess && <p className="phone-success">{phoneSuccess}</p>}
          
          <div className="whatsapp-test-section">
            <p className="whatsapp-description">
              Once your phone number is saved, you can send test WhatsApp alerts with your current business health score and urgent reorder items.
            </p>
            <button 
              className="btn-secondary" 
              onClick={handleSendWhatsApp}
            >
              Send Test WhatsApp Alert
            </button>
          </div>
        </div>
      </section>

      <section className="signout-card card-interactive">
        <div className="section-head">
          <span className="section-eyebrow">Account</span>
          <h2 className="section-title">Sign Out</h2>
        </div>
        <div className="settings-actions">
          <p>Sign out of your storefront and return to the authentication screen.</p>
          <button className="btn-primary" type="button" onClick={signOut}>Sign Out</button>
        </div>
      </section>
    </div>
  )
}
