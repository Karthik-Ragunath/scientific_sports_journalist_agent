import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './ArticleDisplay.css'

function ArticleDisplay({ articles, isProcessing, onTweet, tweetStatus = {} }) {
  const containerRef = useRef(null)
  const [copiedId, setCopiedId] = useState(null)

  useEffect(() => {
    if (containerRef.current && articles.length > 0) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [articles])

  const handleCopy = async (articleId, content) => {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedId(articleId)
      setTimeout(() => setCopiedId(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const getTweetButtonContent = (articleId) => {
    const status = tweetStatus[articleId]
    if (status === 'posting') {
      return (
        <svg className="spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" strokeDasharray="60" strokeDashoffset="20" />
        </svg>
      )
    }
    if (status?.success) {
      return (
        <svg viewBox="0 0 24 24" fill="currentColor">
          <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
        </svg>
      )
    }
    return (
      <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
      </svg>
    )
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
                    className={`share-btn twitter ${tweetStatus[article.id]?.success ? 'success' : ''} ${tweetStatus[article.id] === 'posting' ? 'loading' : ''}`}
                    onClick={() => onTweet && onTweet(article.id, article.content)}
                    disabled={tweetStatus[article.id] === 'posting' || tweetStatus[article.id]?.success}
                    title={tweetStatus[article.id]?.success ? 'Posted to X!' : 'Post to X'}
                  >
                    {getTweetButtonContent(article.id)}
                  </button>
                  {tweetStatus[article.id]?.success && (
                    <a
                      href={tweetStatus[article.id].url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="tweet-link"
                    >
                      View
                    </a>
                  )}
                  <button
                    className={`share-btn copy ${copiedId === article.id ? 'success' : ''}`}
                    onClick={() => handleCopy(article.id, article.content)}
                    title={copiedId === article.id ? 'Copied!' : 'Copy to clipboard'}
                  >
                    {copiedId === article.id ? (
                      <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                      </svg>
                    ) : (
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="9" y="9" width="13" height="13" rx="2"/>
                        <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                      </svg>
                    )}
                  </button>
                </div>
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
