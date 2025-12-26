# OmniShuffle

[![Version](https://img.shields.io/github/v/release/ronilaukkarinen/omnishuffle?style=for-the-badge&label=Version)](https://github.com/ronilaukkarinen/omnishuffle/releases)
![Built with Python](https://img.shields.io/badge/Built%20with-Python-blue?style=for-the-badge&logo=python&logoColor=white)
![License MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Platform Linux](https://img.shields.io/badge/Platform-Linux-orange?style=for-the-badge&logo=linux&logoColor=white)
![Last.fm Scrobbling](https://img.shields.io/badge/Last.fm-Scrobbling-red?style=for-the-badge&logo=lastdotfm&logoColor=white)

A unified command-line music shuffler that combines Spotify, Pandora, and YouTube Music into a single streaming experience with pianobar-style controls and Last.fm scrobbling support.

## Features

- Shuffle music across multiple streaming services simultaneously
- **Spotify Connect support** - 320kbps Premium streaming via spotifyd/librespot
- Pianobar-style single-key controls for seamless interaction
- Built-in Last.fm scrobbling with real-time now playing updates
- Last.fm-based music discovery using similar artists/tracks
- Pandora QuickMix support with automatic Tor proxy for geographic restrictions
- Modern progress bar with brand colors and audio quality display
- Genre tags from Last.fm shown in real-time
- Heart icon (♥) for tracks loved on Last.fm
- Love tracks synced to both Last.fm AND source service
- Endless playback - queue auto-refills when empty

## Requirements

- Python 3.11+
- mpv (with libmpv)
- ffmpeg
- pipx (recommended for installation)
- Tor (optional, for Pandora outside USA - auto-starts when needed)
- spotifyd or librespot (optional, for Spotify 320kbps streaming)

## Installation

### Using pipx (recommended)

```bash
git clone https://github.com/ronilaukkarinen/omnishuffle.git
cd omnishuffle
pipx install -e .
```

### Using pip

```bash
git clone https://github.com/ronilaukkarinen/omnishuffle.git
cd omnishuffle
pip install -e .
```

## Usage

Simply run:

```bash
omnishuffle
```

The player will start shuffling music from all configured sources.

### Status display

```
▄▆ [SPOTIFY] Artist - Song Title ♥  (rock, metal)
━━━━━━━━╸──────────────── 2:42/5:28  320kbps vorbis ⚡  vol 100%
```

- Brand-colored progress bar (green=Spotify, blue=Pandora, red=YouTube)
- ⚡ indicates Spotify Connect (320kbps)
- ♥ indicates track is loved on Last.fm
- Genre tags from Last.fm

## Controls

| Key | Action |
|-----|--------|
| `n` | Next track |
| `p` | Pause/Resume |
| `Space` | Pause/Resume |
| `+` | Love current track (syncs to Last.fm + source) |
| `-` | Ban current track (Pandora) |
| `(` | Volume down |
| `)` | Volume up |
| `l` | Refresh Last.fm recommendations |
| `i` | Show track info (genres, quality, queue size) |
| `S` | Shuffle queue |
| `h` | Show help |
| `q` | Quit |

## Configuration

Configuration is stored in `~/.config/omnishuffle/config.json`.

### Complete example config

```json
{
  "general": {
    "default_mode": "shuffle",
    "sources": ["spotify", "pandora", "youtube"],
    "volume": 80
  },
  "spotify": {
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "redirect_uri": "http://127.0.0.1:8080"
  },
  "pandora": {
    "email": "your@email.com",
    "password": "your_password",
    "proxy": "socks5://127.0.0.1:9050"
  },
  "lastfm": {
    "api_key": "your_api_key",
    "api_secret": "your_shared_secret",
    "username": "your_lastfm_username",
    "password": "your_lastfm_password"
  }
}
```

## Spotify setup

### Basic setup (plays via YouTube)

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click **Create app**
3. Fill in the details:
   - App name: `OmniShuffle`
   - Redirect URI: `http://127.0.0.1:8080` (click Add)
   - Which API/SDKs: Select **Web API**
4. Click **Save**, then **Settings**
5. Copy the **Client ID** and **Client Secret**

On first run, a browser opens for authorization.

### Spotify Connect setup (320kbps Premium streaming)

For true 320kbps Spotify quality, install spotifyd:

```bash
# Arch Linux
yay -S spotifyd

# Or install librespot directly
yay -S librespot
```

Configure spotifyd (`~/.config/spotifyd/spotifyd.conf`):

```ini
[global]
username = "your_spotify_username"
password = "your_spotify_password"
device_name = "OmniShuffle"
device_type = "computer"
bitrate = 320
backend = "pulseaudio"
```

Start spotifyd:

```bash
systemctl --user enable --now spotifyd
```

OmniShuffle will automatically detect the spotifyd device and use it for Spotify tracks at 320kbps. You'll see:

```
✓ Spotify connected (320kbps via OmniShuffle)
```

If no Spotify Connect device is found, it falls back to YouTube:

```
✓ Spotify connected (via YouTube fallback)
```

## Pandora setup

Pandora is only available in the USA. For users outside the USA, OmniShuffle auto-starts Tor with US exit nodes.

### Creating a Pandora account (outside USA)

1. Install Tor: `sudo pacman -S tor`
2. Use Tor Browser or configure your browser to use SOCKS5 proxy `127.0.0.1:9050`
3. Go to [pandora.com](https://www.pandora.com) and create a free account
4. Create some stations based on artists/songs you like

### Configuration

```json
{
  "pandora": {
    "email": "your@email.com",
    "password": "your_password",
    "proxy": "socks5://127.0.0.1:9050"
  }
}
```

OmniShuffle will:
- Auto-start Tor with US exit nodes
- Verify the exit node is in the US
- Retry with a new circuit if needed
- Use QuickMix (Shuffle) station that mixes from all your selected stations

If you're in the USA, leave proxy empty or omit it.

## YouTube Music setup (optional)

YouTube Music works without authentication - OmniShuffle searches YouTube and plays via yt-dlp.

Authentication is only needed for personal playlists. See the detailed setup in the wiki if needed.

## Last.fm integration

OmniShuffle has built-in Last.fm support - no external scrobblers needed.

Features:
- Real-time "now playing" updates
- Automatic scrobbling (after 50% or 4 minutes)
- Love track sync (pressing `+` loves on Last.fm + source service)
- Smart recommendations based on your listening history

### Getting Last.fm API credentials

1. Go to [Last.fm API account creation](https://www.last.fm/api/account/create)
2. Fill in the form (Application name: `OmniShuffle`)
3. Copy the **API Key** and **Shared Secret**

### Configuration

```json
{
  "lastfm": {
    "api_key": "your_api_key",
    "api_secret": "your_shared_secret",
    "username": "your_lastfm_username",
    "password": "your_lastfm_password"
  }
}
```

### How recommendations work

When Last.fm is configured, OmniShuffle uses it as the primary discovery engine:

1. Fetches your loved tracks and top artists from Last.fm
2. Finds similar tracks and artists using Last.fm's database
3. Searches for these on YouTube Music
4. Mixes with Pandora's personalized radio
5. Shuffles everything together

Press `l` to refresh recommendations anytime.

## Audio quality

| Source | Quality | Notes |
|--------|---------|-------|
| Spotify Connect | 320kbps Vorbis | Requires spotifyd/librespot + Premium |
| Spotify (YouTube fallback) | ~128-160kbps | When no Connect device available |
| Pandora Free | 64kbps AAC | |
| Pandora Plus | 192kbps | |
| Pandora Premium | 320kbps | |
| YouTube | ~128-160kbps Opus | Best available audio |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      OmniShuffle                            │
├──────────┬──────────┬──────────┬──────────┬────────────────┤
│ Spotify  │ Pandora  │ YouTube  │ Last.fm  │ spotifyd       │
│ (spotipy)│ (pydora) │ (ytmusic)│ (pylast) │ (320kbps)      │
└────┬─────┴────┬─────┴────┬─────┴────┬─────┴───────┬────────┘
     │          │          │          │             │
     │          │          │    recommendations    │
     │          │          │          │         playback
     └──────────┴──────────┴──────────┘             │
                     │                              │
              ┌──────▼──────┐                       │
              │   Shuffle   │◄──────────────────────┘
              │    Queue    │
              └──────┬──────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
   ┌──────────┐           ┌──────────┐
   │   mpv    │           │ Spotify  │
   │(Pandora/ │           │ Connect  │
   │ YouTube) │           │ (320kbps)│
   └────┬─────┘           └──────────┘
        │
        ▼
   ┌──────────┐
   │  pylast  │────► Last.fm (scrobble)
   └──────────┘
```

## Dependencies

| Package | Purpose |
|---------|---------|
| python-mpv | MPV playback control |
| spotipy | Spotify API client |
| pydora | Pandora API client |
| ytmusicapi | YouTube Music API client |
| yt-dlp | YouTube stream extraction |
| pylast | Last.fm scrobbling |
| readchar | Keyboard input |
| rich | Terminal UI |
| httpx | HTTP client with SOCKS |

## Troubleshooting

### Spotify showing "via YouTube fallback"

spotifyd/librespot is not running or not detected. Start it:

```bash
systemctl --user start spotifyd
```

### Pandora "not available in this country"

Tor might have selected a non-US exit node. OmniShuffle retries automatically, but you can also:

```bash
# Check your Tor exit IP
curl --socks5 127.0.0.1:9050 https://ipinfo.io/country
```

### No audio output

Verify mpv is working:

```bash
mpv --no-video "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Re-authorizing Spotify

If you need new scopes (e.g., after updating OmniShuffle):

```bash
rm ~/.config/omnishuffle/spotify_cache
omnishuffle
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

- [pianobar](https://github.com/PromyLOPh/pianobar) for the inspiration
- [spotifyd](https://github.com/Spotifyd/spotifyd) for Spotify Connect
- All the API library maintainers
