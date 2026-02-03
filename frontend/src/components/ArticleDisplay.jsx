import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './ArticleDisplay.css'

const API_BASE = 'http://localhost:8000'

function ArticleDisplay({ articles, isProcessing, videoPath }) {
  const containerRef = useRef(null)
  const [postingStatus, setPostingStatus] = useState({}) // { [articleId]: 'idle' | 'posting' | 'success' | 'error' }
  const [postError, setPostError] = useState(null)
  const [threadInfo, setThreadInfo] = useState({}) // { [articleId]: { count: N, url: ... } }
  
  useEffect(() => {
    if (containerRef.current && articles.length > 0) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [articles])

  // Extract just the tweet summary for quick sharing
  const extractTweetSummary = (content) => {
    const tweetPatterns = [
      /\*\*Tweet\*\*[:\s]*([^\n]+(?:\n(?!\*\*)[^\n]*)*)/i,
      /\*\*Tweet-worthy Summary\*\*[:\s]*([^\n]+(?:\n(?!\*\*)[^\n]*)*)/i,
      /Tweet[:\s]*([^\n]+)/i,
    ]
    
    for (const pattern of tweetPatterns) {
      const match = content.match(pattern)
      if (match && match[1]) {
        let tweet = match[1].trim()
        tweet = tweet.replace(/\*\*/g, '').replace(/\*/g, '').replace(/`/g, '')
        if (!tweet.includes('#')) {
          tweet += ' #GridironVision #SuperBowlLX'
        }
        return tweet.substring(0, 280)
      }
    }
    
    let fallback = content.replace(/\*\*/g, '').replace(/\*/g, '').substring(0, 200)
    return fallback + '... #GridironVision #SuperBowlLX'
  }

  const handlePostToX = async (articleId, content) => {
    setPostingStatus(prev => ({ ...prev, [articleId]: 'posting' }))
    setPostError(null)
    setThreadInfo(prev => ({ ...prev, [articleId]: null }))
    
    // Post full content as a thread with video
    const tweetSummary = extractTweetSummary(content)
    const fullContent = content + '\n\n#GridironVision #SuperBowlLX #AIAnalysis'
    
    try {
      const response = await fetch(`${API_BASE}/api/post-to-x`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          tweet_text: tweetSummary,
          full_content: fullContent,
          video_path: videoPath || null  // Include video from recording
        })
      })
      
      const result = await response.json()
      
      if (result.success) {
        setPostingStatus(prev => ({ ...prev, [articleId]: 'success' }))
        
        // Store thread info
        if (result.thread_ids && result.thread_ids.length > 1) {
          setThreadInfo(prev => ({ 
            ...prev, 
            [articleId]: { 
              count: result.thread_ids.length, 
              url: result.tweet_url 
            } 
          }))
        }
        
        // Open the tweet in a new tab
        if (result.tweet_url) {
          window.open(result.tweet_url, '_blank')
        }
        
        // Reset status after 5 seconds (longer to show thread info)
        setTimeout(() => {
          setPostingStatus(prev => ({ ...prev, [articleId]: 'idle' }))
        }, 5000)
      } else {
        setPostingStatus(prev => ({ ...prev, [articleId]: 'error' }))
        setPostError(result.error || 'Failed to post')
        setTimeout(() => {
          setPostingStatus(prev => ({ ...prev, [articleId]: 'idle' }))
          setPostError(null)
        }, 5000)
      }
    } catch (err) {
      setPostingStatus(prev => ({ ...prev, [articleId]: 'error' }))
      setPostError(err.message)
      setTimeout(() => {
        setPostingStatus(prev => ({ ...prev, [articleId]: 'idle' }))
        setPostError(null)
      }, 5000)
    }
  }

  const handleCopy = async (content) => {
    try {
      await navigator.clipboard.writeText(content)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  return (
    <div className="article-display" ref={containerRef}>
      {articles.length === 0 && !isProcessing ? (
        <div className="empty-state">
          <div className="empty-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V9a2 2 0 012-2h2a2 2 0 012 2v9a2 2 0 01-2 2h-2z"/>
              <path d="M7 8h6M7 12h8M7 16h4"/>
            </svg>
          </div>
          <h3>Ready for Analysis</h3>
          <p>Use the microphone or type your question below. Our AI will generate real-time insights and analysis.</p>
          <div className="empty-features">
            <div className="feature">
              <span className="feature-icon">📊</span>
              <span>Play Breakdown</span>
            </div>
            <div className="feature">
              <span className="feature-icon">🎯</span>
              <span>Strategic Analysis</span>
            </div>
            <div className="feature">
              <span className="feature-icon">📝</span>
              <span>Tweet Generation</span>
            </div>
          </div>
        </div>
      ) : (
        <AnimatePresence mode="popLayout">
          {articles.map((article, index) => (
            <motion.article
              key={article.id}
              className="article-card"
              initial={{ opacity: 0, y: 30, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            >
              <div className="article-header">
                <div className="article-meta">
                  <span className="article-number">#{String(index + 1).padStart(2, '0')}</span>
                  <span className="article-time">{article.timestamp}</span>
                </div>
                <div className="article-badge">AI GENERATED</div>
              </div>
              {article.query && (
                <div className="article-query">
                  <span className="query-label">Q:</span>
                  <span className="query-text">{article.query}</span>
                </div>
              )}
              <div className="article-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {article.content}
                </ReactMarkdown>
              </div>
              <div className="article-footer">
                <div className="share-buttons">
                  <button 
                    className={`share-btn twitter ${postingStatus[article.id] || ''}`}
                    onClick={() => handlePostToX(article.id, article.content)}
                    disabled={postingStatus[article.id] === 'posting'}
                    title={
                      postingStatus[article.id] === 'posting' ? 'Uploading video & posting thread...' :
                      postingStatus[article.id] === 'success' ? 'Posted with video!' :
                      postingStatus[article.id] === 'error' ? 'Failed - try again' :
                      'Post full analysis + video to X'
                    }
                  >
                    {postingStatus[article.id] === 'posting' ? (
                      <div className="btn-spinner"></div>
                    ) : postingStatus[article.id] === 'success' ? (
                      <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                      </svg>
                    ) : (
                      <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                      </svg>
                    )}
                  </button>
                  <button 
                    className="share-btn copy"
                    onClick={() => handleCopy(article.content)}
                    title="Copy full analysis"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="9" y="9" width="13" height="13" rx="2"/>
                      <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                    </svg>
                  </button>
                </div>
                {postingStatus[article.id] === 'success' && threadInfo[article.id] && (
                  <div className="post-success">
                    ✓ Posted as {threadInfo[article.id].count}-tweet thread with video!
                  </div>
                )}
                {postingStatus[article.id] === 'error' && postError && (
                  <div className="post-error">{postError}</div>
                )}
              </div>
            </motion.article>
          ))}
          
          {isProcessing && (
            <motion.div
              className="processing-card"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              <div className="processing-animation">
                <div className="processing-dots">
                  {[...Array(3)].map((_, i) => (
                    <motion.span
                      key={i}
                      animate={{ y: [0, -10, 0] }}
                      transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.2 }}
                    />
                  ))}
                </div>
              </div>
              <p>Analyzing your question with Gemini AI...</p>
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  )
}

export default ArticleDisplay
