"""MPV-based player with Spotify Connect support for Premium users."""

import mpv
import time
import threading
from dataclasses import dataclass
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from omnishuffle.sources.spotify import SpotifySource


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
    """MPV player wrapper with Spotify Connect support for Premium users."""

    def __init__(self):
        self._create_mpv()
        self.current_track: Optional[Track] = None
        self.paused = False
        self._on_track_end: Optional[Callable] = None
        self._on_time_update: Optional[Callable] = None
        self._play_count = 0  # Track play() calls to detect stale callbacks
        self._loading = False  # True while loading a new track

        # Spotify state
        self._spotify_source: Optional["SpotifySource"] = None
        self._spotify_device_id: Optional[str] = None
        self._using_spotify_connect = False
        self._using_librespot = False
        self._spotify_start_time: Optional[float] = None  # When playback started
        self._spotify_paused_position: float = 0.0  # Position when paused
        self._temp_file: Optional[str] = None  # For librespot temp files

    def _create_mpv(self):
        """Create a fresh MPV instance."""
        self.mpv = mpv.MPV(
            ytdl=True,
            video=False,
            terminal=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
            ytdl_format="bestaudio/best",
        )

        @self.mpv.property_observer('time-pos')
        def on_time(name, value):
            if value is not None and self._on_time_update and not self._using_spotify_connect:
                self._on_time_update(value)

        @self.mpv.event_callback('end-file')
        def on_end_file(event):
            # Only trigger callback if track ended naturally (EOF, not error/stop)
            if hasattr(event, 'data') and hasattr(event.data, 'reason'):
                is_eof = event.data.reason == event.data.EOF
                if is_eof and self._on_track_end and not self._loading:
                    self._on_track_end()

    def set_spotify_source(self, source: "SpotifySource"):
        """Set the Spotify source for Connect playback."""
        self._spotify_source = source
        # Try to find a Spotify Connect device
        device = source.get_connect_device()
        if device:
            self._spotify_device_id = device.get("id")

    def _get_spotify_position(self) -> float:
        """Calculate Spotify position from local timer."""
        if self.paused:
            return self._spotify_paused_position
        if self._spotify_start_time is None:
            return 0.0
        return time.time() - self._spotify_start_time + self._spotify_paused_position


    def play(self, track: Track):
        """Play a track using librespot, Spotify Connect, or mpv."""
        # Increment play count to invalidate any pending callbacks
        self._play_count += 1
        current_play_count = self._play_count

        # Mark as loading - position will return 0 until playback starts
        self._loading = True

        # Only pause Spotify Connect if switching to a non-Spotify source
        # (start_playback will automatically override if staying on Spotify)
        if self._using_spotify_connect and self._spotify_source and track.source != "spotify":
            try:
                self._spotify_source.pause_playback(self._spotify_device_id)
            except Exception:
                pass
        self._using_spotify_connect = False
        self._using_librespot = False

        # Clean up previous temp file
        if self._temp_file:
            try:
                import os
                os.unlink(self._temp_file)
            except Exception:
                pass
            self._temp_file = None

        self.current_track = track
        self.paused = False

        # Try librespot for Spotify tracks (320kbps direct streaming)
        if track.source == "spotify" and self._spotify_source:
            if self._spotify_source.has_direct_streaming:
                stream_file = self._spotify_source.get_stream_file(track)
                if stream_file:
                    self._using_librespot = True
                    self._temp_file = stream_file
                    self.mpv.title = track.title
                    self.mpv.force_media_title = f"{track.artist} - {track.title}"
                    self.mpv.command('loadfile', stream_file, 'replace')
                    self.mpv.pause = False
                    self._loading = False
                    return

        # Try Spotify Connect for Spotify tracks
        if track.source == "spotify" and self._spotify_device_id and self._spotify_source:
            if self._spotify_source.play_track_on_device(track, self._spotify_device_id):
                # Stop mpv if it was playing (Pandora/YouTube)
                try:
                    self.mpv.command('stop')
                except Exception:
                    pass
                self._using_spotify_connect = True
                self._loading = False
                # Start local timer for position tracking
                self._spotify_start_time = time.time()
                self._spotify_paused_position = 0.0
                return

        # Play via mpv (YouTube search for Spotify, direct URL for others)
        self.mpv.title = track.title
        self.mpv.force_media_title = f"{track.artist} - {track.title}"

        url = track.url
        if track.source == "spotify" and not url.startswith("http"):
            url = f"ytdl://ytsearch1:{track.artist} - {track.title}"

        self.mpv.command('loadfile', url, 'replace')
        self.mpv.pause = False
        # _loading will be cleared when time-pos becomes valid

    def pause(self):
        """Toggle pause."""
        if self._using_spotify_connect and self._spotify_source:
            if not self.paused:
                # Pausing - save current position
                self._spotify_paused_position = self._get_spotify_position()
                self._spotify_source.pause_playback(self._spotify_device_id)
            else:
                # Resuming - reset start time
                self._spotify_start_time = time.time()
                self._spotify_source.resume_playback(self._spotify_device_id)
            self.paused = not self.paused
        else:
            self.paused = not self.paused
            self.mpv.pause = self.paused

    def stop(self):
        """Stop playback."""
        self._using_spotify_connect = False
        if self._spotify_source and self._spotify_device_id:
            self._spotify_source.pause_playback(self._spotify_device_id)
        self.mpv.stop()
        self.current_track = None

    def set_volume(self, volume: int):
        """Set volume (0-100)."""
        volume = max(0, min(100, volume))
        self.mpv.volume = volume
        if self._using_spotify_connect and self._spotify_source:
            self._spotify_source.set_volume(volume, self._spotify_device_id)

    def volume_up(self, step: int = 5):
        """Increase volume."""
        self.set_volume(int(self.mpv.volume or 50) + step)

    def volume_down(self, step: int = 5):
        """Decrease volume."""
        self.set_volume(int(self.mpv.volume or 50) - step)

    @property
    def position(self) -> float:
        """Current playback position in seconds."""
        if self._using_spotify_connect:
            return self._get_spotify_position()
        try:
            # Try time-pos first, fall back to playback-time
            pos = self.mpv.time_pos
            if pos is None:
                pos = self.mpv.playback_time
            if pos is not None:
                return float(pos)
            return 0.0
        except Exception:
            return 0.0

    @property
    def duration(self) -> float:
        """Track duration in seconds."""
        if self.current_track and self.current_track.duration > 0:
            return self.current_track.duration
        # Fall back to mpv duration for YouTube/unknown tracks
        try:
            mpv_dur = self.mpv.duration
            if mpv_dur and mpv_dur > 0:
                # Update track duration for scrobbling
                if self.current_track:
                    self.current_track.duration = int(mpv_dur)
                return float(mpv_dur)
        except Exception:
            pass
        return 0

    @property
    def volume(self) -> int:
        """Current volume."""
        return int(self.mpv.volume or 50)

    @property
    def is_spotify_connect(self) -> bool:
        """Check if using Spotify Connect."""
        return self._using_spotify_connect

    @property
    def is_librespot(self) -> bool:
        """Check if using librespot direct streaming."""
        return self._using_librespot

    @property
    def is_spotify_direct(self) -> bool:
        """Check if using any direct Spotify streaming (Connect or librespot)."""
        return self._using_spotify_connect or self._using_librespot

    @property
    def spotify_device_name(self) -> Optional[str]:
        """Get Spotify Connect device name if available."""
        if self._spotify_source and self._spotify_device_id:
            device = self._spotify_source.get_connect_device()
            if device:
                return device.get("name")
        return None

    @property
    def audio_codec(self) -> str:
        """Current audio codec."""
        if self._using_spotify_connect or self._using_librespot:
            return "vorbis"  # Spotify uses Ogg Vorbis
        try:
            return self.mpv.audio_codec_name or ""
        except Exception:
            return ""

    @property
    def audio_bitrate(self) -> int:
        """Current audio bitrate in kbps."""
        if self._using_spotify_connect or self._using_librespot:
            return 320  # Spotify Premium = 320kbps
        try:
            bitrate = self.mpv.audio_bitrate
            return int(bitrate / 1000) if bitrate else 0
        except Exception:
            return 0

    @property
    def sample_rate(self) -> int:
        """Audio sample rate in Hz."""
        if self._using_spotify_connect:
            return 44100  # Spotify uses 44.1kHz
        try:
            params = self.mpv.audio_params
            return params.get("samplerate", 0) if params else 0
        except Exception:
            return 0

    def on_track_end(self, callback: Callable):
        """Register callback for when track ends."""
        self._on_track_end = callback

    def on_time_update(self, callback: Callable):
        """Register callback for time updates."""
        self._on_time_update = callback

    def shutdown(self):
        """Clean shutdown."""
        # Stop Spotify Connect playback
        if self._spotify_source:
            try:
                self._spotify_source.pause_playback(self._spotify_device_id)
            except Exception:
                pass
        # Stop and terminate mpv
        try:
            self.mpv.command('stop')
            self.mpv.terminate()
        except Exception:
            pass
