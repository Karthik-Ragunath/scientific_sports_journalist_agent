import { motion, AnimatePresence } from 'framer-motion'
import './RecordButton.css'

function RecordButton({ isRecording, onStart, onStop }) {
  const handleClick = () => {
    if (isRecording) {
      onStop()
    } else {
      onStart()
    }
  }

  return (
    <motion.button
      className={`record-button ${isRecording ? 'recording' : ''}`}
      onClick={handleClick}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      title={isRecording ? 'Stop recording' : 'Start screen recording'}
    >
      {/* Pulsing ring when recording */}
      <AnimatePresence>
        {isRecording && (
          <>
            <motion.div
              className="pulse-ring"
              initial={{ scale: 1, opacity: 0.5 }}
              animate={{ scale: 1.8, opacity: 0 }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <motion.div
              className="pulse-ring delay"
              initial={{ scale: 1, opacity: 0.5 }}
              animate={{ scale: 1.8, opacity: 0 }}
              transition={{ duration: 1.5, repeat: Infinity, delay: 0.5 }}
            />
          </>
        )}
      </AnimatePresence>
      
      {/* Button background */}
      <div className="record-bg">
        <div className="record-inner">
          {isRecording ? (
            <motion.div 
              className="stop-square"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 500 }}
            />
          ) : (
            <motion.div 
              className="record-circle"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 500 }}
            />
          )}
        </div>
      </div>
      
      {/* Label */}
      <span className="record-label">
        {isRecording ? 'STOP' : 'REC'}
      </span>
    </motion.button>
  )
}

export default RecordButton
