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
