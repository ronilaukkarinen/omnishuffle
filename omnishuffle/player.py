"""MPV-based player with MPRIS support for Last.fm scrobbling."""

import mpv
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Track:
    """Represents a track from any source."""
    title: str
    artist: str
    album: str
    duration: int  # seconds
    url: str  # stream URL or YouTube URL
    source: str  # 'spotify', 'pandora', 'youtube'
    artwork_url: Optional[str] = None
    track_id: Optional[str] = None  # service-specific ID


class Player:
    """MPV player wrapper with MPRIS metadata for scrobbling."""

    def __init__(self):
        self.mpv = mpv.MPV(
            ytdl=True,
            video=False,
            terminal=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
            script='/usr/lib/mpv-mpris/mpris.so',
        )
        self.current_track: Optional[Track] = None
        self.paused = False
        self._on_track_end: Optional[Callable] = None
        self._on_time_update: Optional[Callable] = None

        # Set up event handlers
        @self.mpv.property_observer('eof-reached')
        def on_eof(name, value):
            if value and self._on_track_end:
                self._on_track_end()

        @self.mpv.property_observer('time-pos')
        def on_time(name, value):
            if value is not None and self._on_time_update:
                self._on_time_update(value)

    def play(self, track: Track):
        """Play a track and set MPRIS metadata."""
        self.current_track = track
        self.paused = False

        # Set metadata for MPRIS (rescrobbled will pick this up)
        self.mpv.title = track.title
        self.mpv.force_media_title = f"{track.artist} - {track.title}"

        # For Spotify tracks, we search YouTube
        url = track.url
        if track.source == "spotify" and not url.startswith("http"):
            # Ensure proper yt-dlp search format
            url = f"ytdl://ytsearch1:{track.artist} - {track.title}"

        # Play the URL
        self.mpv.play(url)

    def pause(self):
        """Toggle pause."""
        self.paused = not self.paused
        self.mpv.pause = self.paused

    def stop(self):
        """Stop playback."""
        self.mpv.stop()
        self.current_track = None

    def set_volume(self, volume: int):
        """Set volume (0-100)."""
        self.mpv.volume = max(0, min(100, volume))

    def volume_up(self, step: int = 5):
        """Increase volume."""
        self.set_volume(int(self.mpv.volume or 50) + step)

    def volume_down(self, step: int = 5):
        """Decrease volume."""
        self.set_volume(int(self.mpv.volume or 50) - step)

    @property
    def position(self) -> float:
        """Current playback position in seconds."""
        return self.mpv.time_pos or 0

    @property
    def duration(self) -> float:
        """Track duration in seconds."""
        return self.mpv.duration or 0

    @property
    def volume(self) -> int:
        """Current volume."""
        return int(self.mpv.volume or 50)

    def on_track_end(self, callback: Callable):
        """Register callback for when track ends."""
        self._on_track_end = callback

    def on_time_update(self, callback: Callable):
        """Register callback for time updates."""
        self._on_time_update = callback

    def shutdown(self):
        """Clean shutdown."""
        self.mpv.terminate()
