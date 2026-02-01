import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import './MicButton.css'

function MicButton({ onAudioCapture, isRecording, setIsRecording, isProcessing, disabled }) {
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const streamRef = useRef(null)

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      })
      
      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []
      
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }
      
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        onAudioCapture(blob)
        
        // Clean up stream
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop())
        }
      }
      
      mediaRecorder.start()
      setIsRecording(true)
    } catch (error) {
      console.error('Error accessing microphone:', error)
      alert('Unable to access microphone. Please check permissions.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
    }
  }

  const handleClick = () => {
    if (isProcessing || disabled) return
    
    if (isRecording) {
      stopRecording()
    } else {
      startRecording()
    }
  }

  const isDisabled = isProcessing || disabled

  return (
    <motion.button
      className={`mic-button ${isRecording ? 'recording' : ''} ${isProcessing ? 'processing' : ''} ${isDisabled ? 'disabled' : ''}`}
      onClick={handleClick}
      disabled={isDisabled}
      whileHover={{ scale: isDisabled ? 1 : 1.05 }}
      whileTap={{ scale: isDisabled ? 1 : 0.95 }}
      title={disabled ? 'Record a video first' : isRecording ? 'Stop recording' : 'Ask about the play'}
    >
      {/* Outer ring animation */}
      <AnimatePresence>
        {isRecording && (
          <motion.div
            className="recording-ring"
            initial={{ scale: 1, opacity: 0 }}
            animate={{ scale: 1.5, opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        )}
      </AnimatePresence>
      
      {/* Button background */}
      <div className="button-bg">
        <div className="button-inner">
          {isProcessing ? (
            <div className="spinner">
              <svg viewBox="0 0 50 50">
                <circle cx="25" cy="25" r="20" fill="none" strokeWidth="4" />
              </svg>
            </div>
          ) : isRecording ? (
            <div className="stop-icon">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="2" />
              </svg>
            </div>
          ) : (
            <div className="mic-icon">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
              </svg>
            </div>
          )}
        </div>
      </div>
      
      {/* Sound wave visualization when recording */}
      {isRecording && (
        <div className="sound-waves">
          {[...Array(5)].map((_, i) => (
            <motion.div
              key={i}
              className="wave-bar"
              animate={{
                scaleY: [1, 2, 1],
              }}
              transition={{
                duration: 0.5,
                repeat: Infinity,
                delay: i * 0.1,
              }}
            />
          ))}
        </div>
      )}
    </motion.button>
  )
}

export default MicButton
