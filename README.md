# 🏈 Gridiron Vision - AI Sports Journalist

> **Super Bowl LX Edition** | Bay Area • Levi's Stadium, Santa Clara

An AI-powered sports journalism platform that analyzes live game footage in real-time using Google Gemini. Record plays, ask questions via voice or text, and get instant data-driven analysis in the style of Todd Whitehead.

![Bay Area Theme](https://img.shields.io/badge/Super%20Bowl-LX-orange)
![Gemini AI](https://img.shields.io/badge/Powered%20by-Gemini%20AI-blue)
![Pipecat](https://img.shields.io/badge/Voice-Pipecat-green)

---

## 🎬 Demo Video

**Watch the submission video to see Gridiron Vision in action:**

<video src="submission/submission_video.mp4" controls width="100%">
  Your browser does not support the video tag.
</video>

> 📹 If the video doesn't load above, view it directly: [submission/submission_video.mp4](submission/submission_video.mp4)

**The demo showcases:**
- ✅ Real-time screen recording with audio capture
- ✅ Voice and text-based queries about game plays
- ✅ AI-powered analysis with data visualizations
- ✅ Bay Area-themed UI for Super Bowl LX

---

## ✨ Features

- **🎥 Screen Recording** - Capture game footage with synchronized audio
- **🤖 AI Video Analysis** - Analyze plays using Google Gemini's multimodal capabilities
- **🎤 Voice Queries** - Ask questions about plays using your microphone
- **⌨️ Text Queries** - Type questions via chat interface
- **📊 Data-Driven Output** - Get analysis with tables, stats, and tweet-ready summaries
- **🌉 Bay Area Theme** - Beautiful Golden Gate-inspired UI for Super Bowl LX

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ VideoPlayer │  │  MicButton  │  │     ChatInput       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP API
┌────────────────────────────▼────────────────────────────────┐
│                   Backend (FastAPI)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Recording  │  │   Analyze   │  │    Transcribe       │  │
│  │   Control   │  │    Video    │  │      Audio          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                    AI Services                               │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │   Google Gemini     │  │      Pipecat (Optional)     │   │
│  │   - Video Analysis  │  │   - Real-time Voice         │   │
│  │   - Transcription   │  │   - Gemini Live API         │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **AI Models** | Google Gemini (see supported models below) |
| **Voice AI** | Pipecat + Gemini Live (optional) |
| **Backend** | FastAPI, Python 3.12+ |
| **Frontend** | React, Vite, Framer Motion |
| **Recording** | FFmpeg, AVFoundation (macOS) |
| **Audio** | PyAudio, BlackHole 2ch |
| **Storage** | AWS S3 (optional) |

### Supported Gemini Models

| Model | Use Case | Notes |
|-------|----------|-------|
| `gemini-2.0-flash` | Video analysis, transcription | **Default** - Fast & capable |
| `gemini-2.0-flash-exp` | Experimental features | Multimodal live capabilities |
| `gemini-2.0-flash-live` | Real-time streaming | Requires Gemini Live API access |
| `gemini-2.0-pro` | Complex analysis | Higher quality, slower |
| `gemini-3-pro-preview` | Latest capabilities | Preview access required |
| `gemini-1.5-flash` | Fallback option | Stable, well-tested |
| `gemini-1.5-pro` | High-quality analysis | Longer context window |

---

## 📋 Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **FFmpeg** - `brew install ffmpeg`
- **PortAudio** - `brew install portaudio` (for PyAudio)
- **BlackHole 2ch** - [Download](https://existential.audio/blackhole/) (for system audio capture)
- **Google API Key** - [Get one here](https://aistudio.google.com/app/apikey)

---

## 🚀 Quick Start

### 1. Clone & Setup Environment

```bash
# Clone the repository
git clone <repo-url>
cd gemini-superbowl

# Create Python virtual environment
pyenv virtualenv 3.12.12 sports-science-env
pyenv activate sports-science-env

# Or using venv
python -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# Frontend dependencies
cd frontend
npm install
cd ..
```

### 3. Configure Environment

Create a `.env` file in the project root:

```env
# Required: Google Gemini API Key
GOOGLE_API_KEY=your_api_key_here

# Alternative key name (either works)
GEMINI_API_KEY=your_api_key_here

# Optional: AWS for S3 uploads
AWS_PROFILE=hackathon
S3_BUCKET=your-bucket-name
```

### 4. Audio Setup (macOS)

For capturing system audio, configure BlackHole:

1. Install BlackHole 2ch from [existential.audio](https://existential.audio/blackhole/)
2. Open **Audio MIDI Setup** (Applications → Utilities)
3. Create a **Multi-Output Device** combining your speakers + BlackHole 2ch
4. Set this as your system output

See `audio_video_readme.md` for detailed instructions.

### 5. Run the Application

**Terminal 1 - Backend API:**
```bash
uvicorn api:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

---

## 📖 Usage

### Web Interface

1. **Record** - Click the red record button to capture screen + audio
2. **Stop** - Click again to stop recording
3. **Ask** - Use the microphone OR type in the chat box
4. **View** - See AI-generated analysis with stats and insights

### Standalone Scripts

#### Screen Recording with Audio
```bash
python movie_recorder.py --segment-duration 60 --screen 1
```

Options:
- `--segment-duration` - Seconds per video segment (default: 30)
- `--screen` - Display index (default: 1)
- `--audio-device` - Audio input (default: "BlackHole 2ch")
- `--accumulate` - Accumulate segments (each includes previous)
- `--no-transcribe` - Skip audio transcription

#### Voice Transcription
```bash
# Default mode (chunked transcription with Gemini)
python voice_transcriber.py --output transcript.txt --duration 60

# Faster feedback with smaller chunks
python voice_transcriber.py --chunk-seconds 3

# Pipecat mode (requires Gemini Live API access)
python voice_transcriber.py --use-pipecat --output transcript.txt
```

#### Video Analysis
```bash
python gemini_video_analysis.py path/to/video.mp4
```

---

## 🔧 Configuration

### VS Code Launch Configs

The project includes launch configurations in `.vscode/launch.json`:

- **Sports Science Journalist** - Main recorder with 60s segments
- **Voice Transcriber** - 15-second voice transcription

### Recording Quality

Modify in `movie_recorder.py` or via API:
- `quality`: "low", "medium", "high"
- `segment_duration`: seconds per segment
- `accumulate`: True for growing video segments

---

## 🎤 Pipecat Integration

[Pipecat](https://github.com/pipecat-ai/pipecat) provides real-time voice AI capabilities:

```python
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService

# Real-time voice transcription (requires Gemini Live API access)
gemini_live = GeminiLiveLLMService(
    api_key=api_key,
    model="gemini-2.0-flash-live",
)
```

**Note:** Gemini Live API requires special access. The default mode uses chunked audio transcription which works with standard Gemini API.

---

## 🤖 AI Persona

The analysis uses a **Todd Whitehead** persona:

> *"Providing analysis and insight for @SynergySST and @Sportradar. Sharing basketball data in fun and eye-catching ways."*

Output format:
- **Concise** - No fluff
- **Data tables** - Stats in markdown tables
- **Visual** - Charts and formatted data
- **Tweet-ready** - 280-char summaries

---

## 📁 Project Structure

```
gemini-superbowl/
├── api.py                    # FastAPI backend
├── video_analyzer.py         # Gemini video analysis
├── movie_recorder.py         # Screen + audio recording
├── voice_transcriber.py      # Voice transcription
├── screen_recorder.py        # Basic screen recording
├── requirements.txt          # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main React app
│   │   ├── components/      # UI components
│   │   └── *.css            # Bay Area themed styles
│   └── package.json
├── movie_recordings/         # Recorded videos
├── screen_recordings/        # Screen captures
└── .env                      # API keys (create this)
```

---

## 🐛 Troubleshooting

### "No module named 'pyaudio'"
```bash
brew install portaudio
pip install pyaudio
```

### "BlackHole not found"
1. Install from https://existential.audio/blackhole/
2. Restart your Mac
3. Check Audio MIDI Setup

### "Gemini API error 404"
- Ensure you're using `gemini-2.0-flash` (not experimental models)
- Check your API key is valid

### "Video playback too fast"
The recorder uses `-vf fps=30` and `-af aresample=async=1` for proper timing.

---

## 📄 License

MIT License - See LICENSE file for details.

---

## 🙏 Acknowledgments

- **Google Gemini** - Multimodal AI capabilities
- **Pipecat** - Real-time voice AI framework
- **Super Bowl LX** - Bay Area, here we come! 🌉

---

<p align="center">
  <strong>🌉 Made in SF for Super Bowl LX 🏈</strong>
</p>
