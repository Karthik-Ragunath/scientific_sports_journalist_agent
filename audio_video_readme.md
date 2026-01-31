# Screen Recorder with S3 Upload

Records your screen **with audio** continuously and uploads 1-minute video chunks to S3.

## Setup

### 1. Install ffmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html and add to PATH
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure AWS credentials

```bash
# Option 1: Environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret

# Option 2: AWS CLI
aws configure
```

### 4. Audio Setup (IMPORTANT!)

#### macOS - Install BlackHole

macOS blocks direct system audio capture. You need BlackHole:

```bash
brew install blackhole-2ch
```

Then configure Multi-Output Device:
1. Open **Audio MIDI Setup** (Spotlight → "Audio MIDI Setup")
2. Click **+** (bottom left) → **Create Multi-Output Device**
3. Check both **your speakers/headphones** AND **BlackHole 2ch**
4. Right-click the Multi-Output Device → **Use This Device For Sound Output**

Now audio plays through speakers AND gets captured by ffmpeg.

#### Linux - PulseAudio

Usually works out of the box. If not:

```bash
sudo apt install pulseaudio
# Check available sources:
pactl list short sources
```

#### Windows - Enable Stereo Mix

1. Right-click speaker icon → **Sounds**
2. Go to **Recording** tab
3. Right-click empty area → **Show Disabled Devices**
4. Right-click **Stereo Mix** → **Enable**
5. Set Stereo Mix as default

## Usage

```bash
# Basic usage (macOS with BlackHole)
python screen_recorder_s3.py --bucket your-bucket-name

# Specify audio device explicitly
python screen_recorder_s3.py --bucket your-bucket-name --audio-device "BlackHole 2ch"

# With all options
python screen_recorder_s3.py \
    --bucket my-recordings-bucket \
    --region us-west-2 \
    --prefix nba-game-2024 \
    --segment-duration 60 \
    --fps 30 \
    --quality high \
    --audio-device "BlackHole 2ch"
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--bucket` | (required) | S3 bucket name |
| `--region` | us-east-1 | AWS region |
| `--prefix` | recordings | S3 key prefix/folder |
| `--output-dir` | ./recordings | Local temp directory |
| `--segment-duration` | 60 | Chunk duration in seconds |
| `--fps` | 30 | Frames per second |
| `--quality` | medium | low/medium/high |
| `--audio-device` | auto | Audio device name |

## How it works

1. **Recording**: ffmpeg captures screen + audio, saves 1-minute segments locally
2. **Watching**: Background thread monitors for completed segments
3. **Uploading**: Completed segments queued and uploaded to S3
4. **Cleanup**: Local files deleted after successful upload

## For the hackathon

1. Open Prime Video / YouTube with the NBA game fullscreen
2. Run the recorder pointing to your S3 bucket
3. Your AI agent can poll S3 for new segments and process them

```bash
python screen_recorder_s3.py --bucket nba-hackathon --prefix clippers-suns-game
```

Press `Ctrl+C` to stop recording gracefully.

## Troubleshooting

**No audio in recording (macOS):**
- Verify BlackHole installed: `brew list blackhole-2ch`
- Ensure Multi-Output Device is set as system output
- List devices: `ffmpeg -f avfoundation -list_devices true -i ""`

**No audio in recording (Linux):**
- Check PulseAudio: `pactl list short sources`

**No audio in recording (Windows):**
- Ensure Stereo Mix is enabled and set as default
- List devices: `ffmpeg -list_devices true -f dshow -i dummy`

**Permission denied (macOS):**
- System Preferences → Privacy & Security → Screen Recording → Enable Terminal