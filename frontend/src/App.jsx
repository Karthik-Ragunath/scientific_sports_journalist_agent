import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import VideoPlayer from './components/VideoPlayer'
import MicButton from './components/MicButton'
import RecordButton from './components/RecordButton'
import ArticleDisplay from './components/ArticleDisplay'
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
  const [tweetStatus, setTweetStatus] = useState({})

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
          timestamp: new Date().toLocaleTimeString()
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

  const handleTweet = async (articleId, articleContent) => {
    setTweetStatus(prev => ({ ...prev, [articleId]: 'posting' }))
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/api/tweet`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          article: articleContent,
          auto_extract: true
        })
      })

      const result = await response.json()

      if (result.success) {
        setTweetStatus(prev => ({
          ...prev,
          [articleId]: { success: true, url: result.tweet_url }
        }))
      } else {
        throw new Error(result.error || 'Failed to post tweet')
      }
    } catch (err) {
      setError(err.message)
      setTweetStatus(prev => ({ ...prev, [articleId]: 'error' }))
      console.error('Tweet error:', err)
    }
  }

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
            <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
              <ellipse cx="50" cy="50" rx="45" ry="28" stroke="currentColor" strokeWidth="4"/>
              <path d="M50 22 L50 78" stroke="currentColor" strokeWidth="3"/>
              <path d="M35 30 Q50 50 35 70" stroke="currentColor" strokeWidth="2"/>
              <path d="M65 30 Q50 50 65 70" stroke="currentColor" strokeWidth="2"/>
            </svg>
          </div>
          <div className="logo-text">
            <h1>GRIDIRON VISION</h1>
            <span className="tagline">AI SPORTS JOURNALISM</span>
          </div>
        </div>
        <div className="super-bowl-badge">
          <span className="badge-text">SUPER BOWL</span>
          <span className="badge-number">LX</span>
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
          "Where the game meets the algorithm. Every play, decoded."
        </blockquote>
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
            
            {/* Recording & Mic Controls */}
            <div className="controls-container">
              <div className="controls-row">
                <RecordButton 
                  isRecording={isRecording}
                  onStart={handleStartRecording}
                  onStop={handleStopRecording}
                />
                <MicButton 
                  onAudioCapture={handleAudioCapture}
                  isRecording={isMicRecording}
                  setIsRecording={setIsMicRecording}
                  isProcessing={isProcessing}
                  disabled={!currentVideoUrl && !isRecording}
                />
              </div>
              <p className="control-hint">
                {isRecording ? 'Recording screen... Click red button to stop' : 
                 isMicRecording ? 'Listening... Click mic to stop' :
                 isProcessing ? 'AI is analyzing the play...' : 
                 currentVideoUrl ? 'Click mic to ask about the play' :
                 'Click record to capture the game'}
              </p>
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
              onTweet={handleTweet}
              tweetStatus={tweetStatus}
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
          <p>POWERED BY GEMINI AI • SCIENTIFIC SPORTS JOURNALISM</p>
          <div className="footer-decoration">
            <span></span><span></span><span></span>
          </div>
        </div>
      </motion.footer>
    </div>
  )
}

export default App
