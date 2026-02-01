import { useState, useRef } from 'react'
import { motion } from 'framer-motion'
import './ChatInput.css'

function ChatInput({ onSubmit, isProcessing, disabled }) {
  const [message, setMessage] = useState('')
  const inputRef = useRef(null)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!message.trim() || isProcessing || disabled) return
    
    onSubmit(message.trim())
    setMessage('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const isDisabled = isProcessing || disabled

  return (
    <form className="chat-input-form" onSubmit={handleSubmit}>
      <div className={`chat-input-container ${isDisabled ? 'disabled' : ''}`}>
        <input
          ref={inputRef}
          type="text"
          className="chat-input"
          placeholder={disabled ? "Record a video first..." : "Ask about the play..."}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isDisabled}
        />
        <motion.button
          type="submit"
          className={`send-button ${message.trim() ? 'active' : ''}`}
          disabled={isDisabled || !message.trim()}
          whileHover={{ scale: isDisabled || !message.trim() ? 1 : 1.05 }}
          whileTap={{ scale: isDisabled || !message.trim() ? 1 : 0.95 }}
        >
          {isProcessing ? (
            <div className="send-spinner">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" strokeDasharray="60" strokeDashoffset="20" />
              </svg>
            </div>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          )}
        </motion.button>
      </div>
      <div className="input-hint">
        Press <kbd>Enter</kbd> to send or use the mic button
      </div>
    </form>
  )
}

export default ChatInput
