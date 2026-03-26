### 1.3.0: 2026-03-25

* Add audio output device selector at startup (AirPlay, external speakers, etc.)
* Support `--device` flag to set audio device from command line

### 1.2.2: 2026-03-19

* Auto-fix mpv/ffmpeg symbol mismatch on macOS by running `brew reinstall` when libmpv fails to load
* Add mpv/ffmpeg sync check to install script for macOS
* Fix Pandora/YouTube tracks stuck at 0:00 when stream URL fails to load

### 1.2.1: 2026-02-07

* Fix Spotify not stopping on quit by passing `device_id` in stop()

### 1.2.0: 2026-01-18

* Use dedicated Tor port 9150 to avoid conflicts with system Tor
* Retry Pandora 3 times on geo-block, retry Last.fm 3 times on timeout
* Exit if any enabled service fails to connect (Spotify, Pandora, YouTube, Last.fm)

### 1.1.2: 2026-01-13

* Set Spotify volume when track starts playing (fixes quieter Spotify playback)
* Fix Spotify not stopping on quit or track change (pass device_id to pause)

### 1.1.1: 2026-01-13

* Require platform-specific Spotify device, exit if not found (never cross-platform fallback)
* Improve YouTube shuffle diversity by using multiple seed songs instead of one

### 1.1.0: 2026-01-08

* Suppress Spotify API HTTP errors from flooding console output
* Change default volume from 80% to 100%
* Require Last.fm to be configured and working to start
* Fix volume not persisting when track changes
* Show song title and artist in love message

### 1.0.10: 2026-01-07

* Auto-start spotifyd if not running on launch
* Prefer platform-specific Spotify Connect device (OmniShuffle-Mac on macOS, OmniShuffle on Linux)
* Fix Spotify not stopping when pressing n or q (now pauses active device regardless of state)

### 1.0.9: 2026-01-07

* Hide Python dock icon on macOS

### 1.0.8: 2026-01-07

* Fix mpv volume not initialized causing no audio on YouTube/Pandora tracks

### 1.0.7: 2026-01-07

* Add macOS support (cross-platform Tor handling, Homebrew instructions)
* Add `install.sh` interactive installer script for macOS, Arch, Debian/Ubuntu, Fedora

### 1.0.6: 2025-12-28

* Add --spotify, --pandora, --youtube flags to play from specific sources
* YouTube seeding now uses random liked song from entire Spotify library
* Fix help text for ban (works for all sources, not just Pandora)

### 1.0.5: 2025-12-27

* Fix spacing after heart icon
* Shuffle from all Spotify playlists and liked songs combined

### 1.0.4: 2025-12-26

* Show play count from Last.fm after genres (x plays)
* Fix double space before genre tags

### 1.0.3: 2025-12-26

* Fix auto-play next track for Pandora/YouTube (loading flag was not cleared)
* Shuffle Spotify liked songs from random positions in library (not just first 50)
* Fix now playing updates when pressing n multiple times (3-second delay before API call)
* Remove YouTube generic fallback that returned unrelated recommendations
* Fix love message formatting

### 1.0.2: 2025-12-26

* Show version number in startup box

### 1.0.1: 2025-12-26

* Truncate status lines to terminal width to prevent display issues
* Use primary artist for scrobbling with multi-artist tracks
* Fix auto-play next track when Pandora/YouTube song ends

### 1.0.0: 2025-12-26

* Spotify Connect support for 320kbps Premium streaming via spotifyd
* Direct librespot streaming option (for accounts without 2FA)
* Interactive Spotify Connect activation prompt when device not found
* Direct Last.fm scrobbling with pylast (no external dependencies needed)
* Now playing updates to Last.fm in real-time
* Scrobble indicator (✓) shown next to track title when scrobbled
* Love tracks synced to both Last.fm AND source service (Spotify/Pandora)
* Fast startup - loads Spotify liked songs directly instead of slow YouTube searches
* Modern thin progress bar with brand colors
* Audio quality display (bitrate and codec, ⚡ indicator for Spotify Connect)
* Genre tags from Last.fm shown in status and track info
* Loading indicator while fetching tracks
* Start Tor with US exit nodes for Pandora geo-restriction bypass
* Verify US exit node via Tor-friendly service (ipify + ipinfo)
* Retry Pandora login with new Tor circuit if geo-blocked (up to 5 attempts)
* Pandora QuickMix support - uses actual Shuffle station that mixes from all your stations
* Heart icon (♥) shown for tracks loved on Last.fm
* Ban works for all sources - saves to local banned.json and filters from queue
* YouTube seeded recommendations based on Spotify liked songs
* Fix two songs playing at once on track end
* Fix two songs playing when switching between sources
* Fix Spotify timestamp using local timer instead of API polling
* Fix Pandora proxy for all API calls
* Fix display flooding when pressing n or p
* Fix YouTube showing 0:00 duration by using mpv duration
* Show source breakdown in track count
* EQ-style animation for playing indicator
* Volume indicator uses dimmer text color

### 0.1.0: 2025-12-26

* Initial release
* Spotify integration with OAuth authentication
* Pandora integration with Tor proxy support for non-US users
* YouTube Music integration (works without auth for search/recommendations)
* MPV-based playback with MPRIS support for Last.fm scrobbling
* Pianobar-style keyboard controls (n, p, +, -, etc.)
* Unified shuffle queue across all sources
* Radio/recommendations mode
* Live status line with animated spinner showing current track
* Volume control
* Track love/ban support
* Rich terminal UI with brand colors
