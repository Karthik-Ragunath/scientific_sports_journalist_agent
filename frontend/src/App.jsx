import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import VideoPlayer from './components/VideoPlayer'
import MicButton from './components/MicButton'
import RecordButton from './components/RecordButton'
import ArticleDisplay from './components/ArticleDisplay'
import ChatInput from './components/ChatInput'
import './App.css'

const API_BASE = 'http://localhost:8000'

function App() {
  const [isRecording, setIsRecording] = useState(false)
  const [isMicRecording, setIsMicRecording] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [articles, setArticles] = useState([])
  const [currentVideoUrl, setCurrentVideoUrl] = useState(null)
  const [recordingStatus, setRecordingStatus] = useState(null)
  const [error, setError] = useState(null)

  // Check recording status on mount
  useEffect(() => {
    checkRecordingStatus()
  }, [])

  const checkRecordingStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/recording/status`)
      if (response.ok) {
        const status = await response.json()
        setRecordingStatus(status)
        setIsRecording(status.is_recording)
        if (status.video_url) {
          setCurrentVideoUrl(`${API_BASE}${status.video_url}`)
        }
      }
    } catch (err) {
      console.log('Backend not available yet')
    }
  }

  const handleStartRecording = async () => {
    setError(null)
    try {
      const response = await fetch(`${API_BASE}/api/recording/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          segment_duration: 30,
          quality: 'medium'
        })
      })
      
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to start recording')
      }
      
      const status = await response.json()
      setRecordingStatus(status)
      setIsRecording(true)
    } catch (err) {
      setError(err.message)
      console.error('Start recording error:', err)
    }
  }

  const handleStopRecording = async () => {
    setError(null)
    try {
      const response = await fetch(`${API_BASE}/api/recording/stop`, {
        method: 'POST'
      })
      
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to stop recording')
      }
      
      const status = await response.json()
      setRecordingStatus(status)
      setIsRecording(false)
      
      if (status.video_url) {
        setCurrentVideoUrl(`${API_BASE}${status.video_url}`)
      }
    } catch (err) {
      setError(err.message)
      console.error('Stop recording error:', err)
    }
  }

  const handleAudioCapture = async (blob) => {
    setIsProcessing(true)
    setError(null)
    
    try {
      const formData = new FormData()
      formData.append('audio', blob, 'recording.webm')
      
      // If we have a current video, include its path
      if (recordingStatus?.current_video) {
        formData.append('video_path', recordingStatus.current_video)
      }
      
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        body: formData
      })
      
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Analysis failed')
      }
      
      const result = await response.json()
      
      if (result.success && result.analysis) {
        setArticles(prev => [...prev, {
          id: Date.now(),
          content: result.analysis,
          thinking: result.thinking,
          timestamp: new Date().toLocaleTimeString(),
          query: '🎤 Voice query'
        }])
      } else if (result.error) {
        throw new Error(result.error)
      }
    } catch (err) {
      setError(err.message)
      console.error('Analysis error:', err)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleTextSubmit = async (message) => {
    setIsProcessing(true)
    setError(null)
    
    try {
      const formData = new FormData()
      formData.append('query', message)
      
      // If we have a current video, include its path
      if (recordingStatus?.current_video) {
        formData.append('video_path', recordingStatus.current_video)
      }
      
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        body: formData
      })
      
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Analysis failed')
      }
      
      const result = await response.json()
      
      if (result.success && result.analysis) {
        setArticles(prev => [...prev, {
          id: Date.now(),
          content: result.analysis,
          thinking: result.thinking,
          timestamp: new Date().toLocaleTimeString(),
          query: message
        }])
      } else if (result.error) {
        throw new Error(result.error)
      }
    } catch (err) {
      setError(err.message)
      console.error('Analysis error:', err)
    } finally {
      setIsProcessing(false)
    }
  }

  const inputDisabled = !currentVideoUrl && !isRecording

  return (
    <div className="app">
      {/* Animated background elements */}
      <div className="bg-grid"></div>
      <div className="bg-gradient"></div>
      <div className="field-lines"></div>
      
      {/* Header */}
      <motion.header 
        className="header"
        initial={{ y: -100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
      >
        <div className="logo-container">
          <div className="logo-icon">
            {/* Golden Gate Bridge inspired icon */}
            <svg viewBox="0 0 100 80" fill="none" xmlns="http://www.w3.org/2000/svg">
              {/* Left tower */}
              <rect x="15" y="20" width="8" height="50" rx="1" fill="#c04000"/>
              <rect x="17" y="15" width="4" height="8" rx="1" fill="#ff6b35"/>
              
              {/* Right tower */}
              <rect x="77" y="20" width="8" height="50" rx="1" fill="#c04000"/>
              <rect x="79" y="15" width="4" height="8" rx="1" fill="#ff6b35"/>
              
              {/* Main cables */}
              <path d="M5 25 Q19 60 50 55 Q81 60 95 25" stroke="#ff6b35" strokeWidth="3" fill="none"/>
              
              {/* Deck */}
              <rect x="5" y="60" width="90" height="6" rx="2" fill="#c04000"/>
              
              {/* Vertical cables */}
              <line x1="25" y1="38" x2="25" y2="60" stroke="#ff6b35" strokeWidth="1.5"/>
              <line x1="35" y1="48" x2="35" y2="60" stroke="#ff6b35" strokeWidth="1.5"/>
              <line x1="50" y1="54" x2="50" y2="60" stroke="#ff6b35" strokeWidth="1.5"/>
              <line x1="65" y1="48" x2="65" y2="60" stroke="#ff6b35" strokeWidth="1.5"/>
              <line x1="75" y1="38" x2="75" y2="60" stroke="#ff6b35" strokeWidth="1.5"/>
              
              {/* Football overlay */}
              <ellipse cx="50" cy="40" rx="18" ry="10" stroke="#d4af37" strokeWidth="2" fill="none" opacity="0.6"/>
              <line x1="50" y1="30" x2="50" y2="50" stroke="#d4af37" strokeWidth="1.5" opacity="0.6"/>
            </svg>
          </div>
          <div className="logo-text">
            <h1>GRIDIRON VISION</h1>
            <span className="tagline">BAY AREA • AI SPORTS JOURNALISM</span>
          </div>
        </div>
        <div className="super-bowl-badge">
          <span className="badge-text">SUPER BOWL</span>
          <span className="badge-number">LX</span>
          <span className="badge-location">Levi's Stadium • Santa Clara</span>
        </div>
      </motion.header>

      {/* Hero Quote */}
      <motion.div 
        className="hero-quote"
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.3, duration: 0.6 }}
      >
        <blockquote>
          "From the Golden Gate to the gridiron. Every play, decoded by AI."
        </blockquote>
        <div className="location-tag">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
          San Francisco Bay Area, California
        </div>
      </motion.div>

      {/* Error Banner */}
      <AnimatePresence>
        {error && (
          <motion.div 
            className="error-banner"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
          >
            <span>{error}</span>
            <button onClick={() => setError(null)}>×</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <main className="main-content">
        <div className="content-grid">
          {/* Video Section */}
          <motion.section 
            className="video-section"
            initial={{ x: -50, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ delay: 0.5, duration: 0.7 }}
          >
            <div className="section-header">
              <span className="section-number">01</span>
              <h2>LIVE ANALYSIS</h2>
            </div>
            <VideoPlayer videoUrl={currentVideoUrl} isRecording={isRecording} />
            
            {/* Recording Controls */}
            <div className="controls-container">
              <div className="controls-row">
                <RecordButton 
                  isRecording={isRecording}
                  onStart={handleStartRecording}
                  onStop={handleStopRecording}
                />
                <div className="input-divider-vertical"></div>
                <MicButton 
                  onAudioCapture={handleAudioCapture}
                  isRecording={isMicRecording}
                  setIsRecording={setIsMicRecording}
                  isProcessing={isProcessing}
                  disabled={inputDisabled}
                />
              </div>
              
              <p className="control-hint">
                {isRecording ? 'Recording screen... Click red button to stop' : 
                 isMicRecording ? 'Listening... Click mic to stop' :
                 isProcessing ? 'AI is analyzing the play...' : 
                 currentVideoUrl ? 'Use mic or type below to ask about the play' :
                 'Click record to capture the game'}
              </p>

              {/* Chat Input */}
              <div className="chat-section">
                <div className="input-divider">
                  <span>or type your question</span>
                </div>
                <ChatInput 
                  onSubmit={handleTextSubmit}
                  isProcessing={isProcessing}
                  disabled={inputDisabled}
                />
              </div>
            </div>
          </motion.section>

          {/* Articles Section */}
          <motion.section 
            className="articles-section"
            initial={{ x: 50, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ delay: 0.7, duration: 0.7 }}
          >
            <div className="section-header">
              <span className="section-number">02</span>
              <h2>AI INSIGHTS</h2>
            </div>
            <ArticleDisplay 
              articles={articles} 
              isProcessing={isProcessing} 
              videoPath={recordingStatus?.current_video}
            />
          </motion.section>
        </div>
      </main>

      {/* Footer */}
      <motion.footer 
        className="footer"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1, duration: 0.5 }}
      >
        <div className="footer-content">
          <p>POWERED BY GEMINI AI • BAY AREA SPORTS SCIENCE</p>
          <div className="footer-decoration">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span className="bay-badge">
            🌉 Made in SF
          </span>
        </div>
      </motion.footer>
    </div>
  )
}

export default App
