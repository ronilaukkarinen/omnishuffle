"""Last.fm scrobbling support using pylast."""

import time
import threading
from typing import Optional

try:
    import pylast
    PYLAST_AVAILABLE = True
except ImportError:
    PYLAST_AVAILABLE = False

from omnishuffle.player import Track


class Scrobbler:
    """Last.fm scrobbler using pylast."""

    # Scrobble after 50% of track or 4 minutes, whichever comes first
    SCROBBLE_THRESHOLD = 0.5
    SCROBBLE_MAX_TIME = 240  # 4 minutes

    def __init__(self, api_key: str, api_secret: str, username: str, password_hash: str):
        self.network: Optional[pylast.LastFMNetwork] = None
        self.current_track: Optional[Track] = None
        self.track_start_time: Optional[float] = None
        self.scrobbled = False
        self._enabled = False

        if not PYLAST_AVAILABLE:
            return

        try:
            self.network = pylast.LastFMNetwork(
                api_key=api_key,
                api_secret=api_secret,
                username=username,
                password_hash=password_hash,
            )
            self._enabled = True
        except Exception:
            pass

    @property
    def enabled(self) -> bool:
        """Check if scrobbling is enabled."""
        return self._enabled and self.network is not None

    def now_playing(self, track: Track):
        """Update now playing status on Last.fm."""
        if not self.enabled:
            return

        self.current_track = track
        self.track_start_time = time.time()
        self.scrobbled = False

        try:
            self.network.update_now_playing(
                artist=track.artist,
                title=track.title,
                album=track.album or None,
                duration=track.duration if track.duration > 0 else None,
            )
        except Exception:
            pass

    def check_scrobble(self, position: float):
        """Check if we should scrobble based on playback position."""
        if not self.enabled or not self.current_track or self.scrobbled:
            return

        track = self.current_track
        if track.duration <= 0:
            return

        # Check if we've played enough of the track
        played_ratio = position / track.duration
        played_time = position

        if played_ratio >= self.SCROBBLE_THRESHOLD or played_time >= self.SCROBBLE_MAX_TIME:
            self._scrobble()

    def _scrobble(self):
        """Submit scrobble to Last.fm."""
        if not self.enabled or not self.current_track or self.scrobbled:
            return

        track = self.current_track
        timestamp = int(self.track_start_time or time.time())

        try:
            self.network.scrobble(
                artist=track.artist,
                title=track.title,
                album=track.album or None,
                timestamp=timestamp,
            )
            self.scrobbled = True
        except Exception:
            pass

    def love_track(self, track: Track) -> bool:
        """Love a track on Last.fm."""
        if not self.enabled:
            return False

        try:
            lastfm_track = self.network.get_track(track.artist, track.title)
            lastfm_track.love()
            return True
        except Exception:
            return False

    def unlove_track(self, track: Track) -> bool:
        """Unlove a track on Last.fm."""
        if not self.enabled:
            return False

        try:
            lastfm_track = self.network.get_track(track.artist, track.title)
            lastfm_track.unlove()
            return True
        except Exception:
            return False
