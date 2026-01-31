import { useRef, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import './VideoPlayer.css'

function VideoPlayer({ videoUrl, isRecording }) {
  const videoRef = useRef(null)
  const [hasVideo, setHasVideo] = useState(false)
  
  useEffect(() => {
    setHasVideo(!!videoUrl)
  }, [videoUrl])
  
  return (
    <div className="video-player">
      <div className="video-frame">
        {/* Decorative corners */}
        <div className="corner corner-tl"></div>
        <div className="corner corner-tr"></div>
        <div className="corner corner-bl"></div>
        <div className="corner corner-br"></div>
        
        {/* Video container */}
        <div className="video-container">
          {hasVideo ? (
            <video
              ref={videoRef}
              src={videoUrl}
              controls
              autoPlay={false}
              playsInline
            >
              Your browser does not support the video tag.
            </video>
          ) : (
            <div className="video-placeholder">
              {isRecording ? (
                <div className="recording-indicator">
                  <div className="rec-dot"></div>
                  <span>RECORDING SCREEN...</span>
                  <p>Your screen is being captured. Click stop when ready.</p>
                </div>
              ) : (
                <div className="placeholder-content">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                  </svg>
                  <span>NO VIDEO LOADED</span>
                  <p>Click the record button to capture the game</p>
                </div>
              )}
            </div>
          )}
        </div>
        
        {/* Overlay info */}
        <div className="video-overlay">
          <div className={`live-badge ${isRecording ? 'active' : ''}`}>
            <span className="pulse"></span>
            {isRecording ? 'RECORDING' : hasVideo ? 'RECORDED' : 'STANDBY'}
          </div>
        </div>
      </div>
      
      {/* Video info bar */}
      <div className="video-info">
        <div className="info-left">
          <span className="game-label">
            {isRecording ? 'LIVE CAPTURE' : hasVideo ? 'RECORDED PLAY' : 'AWAITING INPUT'}
          </span>
          <h3>{hasVideo ? 'Screen Recording' : 'Ready to Record'}</h3>
        </div>
        <div className="info-right">
          <div className={`stat-box ${hasVideo ? 'active' : ''}`}>
            <span className="stat-value">{hasVideo ? 'HD' : '--'}</span>
            <span className="stat-label">QUALITY</span>
          </div>
          <div className={`stat-box ${hasVideo ? 'active' : ''}`}>
            <span className="stat-value">{hasVideo ? 'AI' : '--'}</span>
            <span className="stat-label">READY</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default VideoPlayer
