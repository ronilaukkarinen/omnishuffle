# OmniShuffle

![Built with Python](https://img.shields.io/badge/Built%20with-Python-blue?style=for-the-badge&logo=python&logoColor=white)
![License MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Platform Linux](https://img.shields.io/badge/Platform-Linux-orange?style=for-the-badge&logo=linux&logoColor=white)
![Last.fm Scrobbling](https://img.shields.io/badge/Last.fm-Scrobbling-red?style=for-the-badge&logo=lastdotfm&logoColor=white)

A unified command-line music shuffler that combines Spotify, Pandora, and YouTube Music into a single streaming experience with pianobar-style controls and Last.fm scrobbling support.

## Features

- Shuffle music across multiple streaming services simultaneously
- Pianobar-style single-key controls for seamless interaction
- Automatic Last.fm scrobbling via MPRIS
- Pandora support with Tor proxy for geographic restrictions
- Radio/recommendations mode using each service's algorithm
- Playlist mode to shuffle from your saved playlists
- Love and ban tracks with single keystrokes

## Requirements

- Python 3.11+
- mpv (with libmpv)
- mpv-mpris (for Last.fm scrobbling)
- ffmpeg
- pipx (recommended for installation)
- Tor (optional, for Pandora outside USA)

## Installation

### Using pipx (recommended)

```bash
git clone https://github.com/yourusername/omnishuffle.git
cd omnishuffle
pipx install -e .
```

### Using pip

```bash
git clone https://github.com/yourusername/omnishuffle.git
cd omnishuffle
pip install -e .
```

## Usage

Simply run:

```bash
omnishuffle
```

The player will start shuffling music from all configured sources.

## Controls

| Key | Action |
|-----|--------|
| `n` | Next track |
| `p` | Pause/Resume |
| `Space` | Pause/Resume |
| `+` | Love current track |
| `-` | Ban current track (Pandora) |
| `(` | Volume down |
| `)` | Volume up |
| `i` | Show track info |
| `S` | Shuffle queue |
| `h` | Show help |
| `q` | Quit |

## Configuration

Configuration is stored in `~/.config/omnishuffle/config.json`.

### Spotify setup

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click **Create app**
3. Fill in the details:
   - App name: `OmniShuffle` (or anything you like)
   - App description: Anything
   - Redirect URI: **must be exactly** `http://127.0.0.1:8080` (click Add)
   - Which API/SDKs are you planning to use?: Select **Web API**
4. Check the terms checkbox and click **Save**
5. Click **Settings** in your new app
6. Copy the **Client ID** and click **View client secret** to copy the secret

Add to your config (`~/.config/omnishuffle/config.json`):

```json
{
  "spotify": {
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "redirect_uri": "http://127.0.0.1:8080"
  }
}
```

**Important:** The redirect URI in your Spotify app settings must match exactly what's in your config. If you get "INVALID_CLIENT: Invalid redirect URI", check that `http://127.0.0.1:8080` is added in your app's Redirect URIs.

On first run, a browser will open for you to authorize the app.

### Pandora setup

Pandora is only available in the USA. For users outside the USA, you'll need Tor.

#### Creating a Pandora account (outside USA)

1. Install and start Tor:
   ```bash
   sudo pacman -S tor
   sudo systemctl start tor
   ```

2. Configure your browser to use SOCKS5 proxy `127.0.0.1:9050`
   - Or use Tor Browser

3. Go to [pandora.com](https://www.pandora.com) and create a free account

4. Create some stations based on artists/songs you like

#### Configuration

Add to your config (`~/.config/omnishuffle/config.json`):

```json
{
  "pandora": {
    "email": "your@email.com",
    "password": "your_password",
    "proxy": "socks5://127.0.0.1:9050"
  }
}
```

If you're in the USA, you can leave the proxy empty:

```json
{
  "pandora": {
    "proxy": ""
  }
}
```

Make sure Tor is running before starting OmniShuffle:

```bash
sudo systemctl start tor
```

### YouTube Music setup (optional)

YouTube Music works without authentication. OmniShuffle will search YouTube and play audio via yt-dlp - no setup needed.

Authentication is **only required** if you want to access your personal YouTube Music playlists and liked songs. If you don't use YouTube Music playlists, skip this section entirely.

#### Creating Google OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)

2. Create a new project:
   - Click the project dropdown at the top
   - Click **New Project**
   - Name it `OmniShuffle` and click **Create**
   - Wait for the project to be created and select it

3. Enable the YouTube Data API:
   - Go to **APIs & Services > Library**
   - Search for "YouTube Data API v3"
   - Click it and click **Enable**

4. Configure OAuth consent screen:
   - Go to **APIs & Services > OAuth consent screen**
   - Select **External** and click **Create**
   - Fill in the required fields:
     - App name: `OmniShuffle`
     - User support email: Your email
     - Developer contact email: Your email
   - Click **Save and Continue**
   - Skip "Scopes" (just click **Save and Continue**)
   - **Important - Add test users:**
     - Click **Add Users**
     - Add your own Google/Gmail email address
     - Click **Save and Continue**
   - Click **Back to Dashboard**

5. Create OAuth credentials:
   - Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth client ID**
   - Application type: **TVs and Limited Input devices** (not Desktop app!)
   - Name: `OmniShuffle`
   - Click **Create**
   - Copy the **Client ID** and **Client Secret**

#### Running the authentication

```bash
~/.local/share/pipx/venvs/omnishuffle/bin/ytmusicapi oauth
```

When prompted:
- Paste your Client ID
- Paste your Client Secret
- A browser will open for you to authorize

Move the generated file:

```bash
mv oauth.json ~/.config/omnishuffle/ytmusic_auth.json
```

Update your config (`~/.config/omnishuffle/config.json`):

```json
{
  "youtube": {
    "auth_file": "/home/yourusername/.config/omnishuffle/ytmusic_auth.json"
  }
}
```

Note: Use the full absolute path, not `~`.

### General settings

```json
{
  "general": {
    "default_mode": "shuffle",
    "sources": ["spotify", "pandora", "youtube"],
    "volume": 80
  }
}
```

Available modes:
- `shuffle` - Shuffle tracks from your playlists across all services
- `radio` - Use each service's recommendation engine

## Last.fm scrobbling

OmniShuffle uses mpv for playback with the mpv-mpris plugin to expose MPRIS metadata. Combined with [rescrobbled](https://github.com/InputUsername/rescrobbled), all your tracks are automatically scrobbled to Last.fm.

### Installing mpv-mpris

```bash
sudo pacman -S mpv-mpris
```

### Installing rescrobbled

```bash
yay -S rescrobbled-git
```

### Getting Last.fm API credentials

1. Go to [Last.fm API account creation](https://www.last.fm/api/account/create)

2. Fill in the form:
   - Application name: `OmniShuffle`
   - Application description: Anything
   - Callback URL: Leave empty
   - Application homepage: Leave empty (or any URL)

3. Click **Submit**

4. Copy the **API Key** and **Shared Secret**

### Configuring rescrobbled

Edit `~/.config/rescrobbled/config.toml`:

```toml
lastfm-key = "your_api_key"
lastfm-secret = "your_shared_secret"
```

### Authenticating with Last.fm

Run rescrobbled once manually to log in:

```bash
rescrobbled
```

It will prompt for your Last.fm username and password. After successful login, press Ctrl+C.

### Enabling the service

```bash
systemctl --user enable --now rescrobbled
```

### Verifying it works

Check the service status:

```bash
systemctl --user status rescrobbled
```

Watch the logs while playing music:

```bash
journalctl --user -u rescrobbled -f
```

All tracks played through OmniShuffle will now be scrobbled to Last.fm automatically.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   OmniShuffle                       │
├──────────┬──────────┬──────────┬───────────────────┤
│ Spotify  │ Pandora  │ YouTube  │ Local files       │
│ (spotipy)│ (pydora) │ (ytmusic)│ (future)          │
└────┬─────┴────┬─────┴────┬─────┴─────┬─────────────┘
     └──────────┴──────────┴───────────┘
                     │
              ┌──────▼──────┐
              │   Shuffle   │
              │    Queue    │
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │     mpv     │◄──── MPRIS ────► rescrobbled
              │  (playback) │                       │
              └─────────────┘                       ▼
                                                Last.fm
```

## Dependencies

| Package | Purpose |
|---------|---------|
| python-mpv | MPV playback control |
| spotipy | Spotify API client |
| pydora | Pandora API client |
| ytmusicapi | YouTube Music API client |
| yt-dlp | YouTube stream extraction |
| readchar | Keyboard input handling |
| rich | Terminal UI formatting |
| httpx | HTTP client with SOCKS support |

## Troubleshooting

### Multiple sources not loading

Check that each service is properly configured by looking at the startup messages. A green checkmark indicates successful connection.

### Pandora not connecting

Ensure Tor is running and accessible on port 9050:

```bash
sudo systemctl status tor
curl --socks5 127.0.0.1:9050 https://check.torproject.org/api/ip
```

### No audio output

Verify mpv is working:

```bash
mpv --no-video "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Scrobbling not working

Check that rescrobbled is running and authenticated:

```bash
systemctl --user status rescrobbled
journalctl --user -u rescrobbled -f
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a pull request.

## Acknowledgments

- [pianobar](https://github.com/PromyLOPh/pianobar) for the inspiration
- [rescrobbled](https://github.com/InputUsername/rescrobbled) for MPRIS scrobbling
- All the API library maintainers
