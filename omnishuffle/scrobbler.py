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
        self._last_error: Optional[str] = None

        if not PYLAST_AVAILABLE:
            self._last_error = "pylast not available"
            return

        try:
            self.network = pylast.LastFMNetwork(
                api_key=api_key,
                api_secret=api_secret,
                username=username,
                password_hash=password_hash,
            )
            # Test connection by getting user info
            self.network.get_user(username)
            self._enabled = True
        except Exception as e:
            self._last_error = str(e)

    @property
    def enabled(self) -> bool:
        """Check if scrobbling is enabled."""
        return self._enabled and self.network is not None

    def now_playing(self, track: Track) -> bool:
        """Update now playing status on Last.fm."""
        if not self.enabled:
            return False

        self.current_track = track
        self.track_start_time = time.time()
        self.scrobbled = False

        try:
            artist = track.artist.strip() if track.artist else ""
            title = track.title.strip() if track.title else ""
            album = track.album.strip() if track.album else None
            duration = track.duration if track.duration and track.duration > 0 else None

            if not artist or not title:
                return False

            self.network.update_now_playing(
                artist=artist,
                title=title,
                album=album,
                duration=duration,
            )
            return True
        except Exception as e:
            self._last_error = f"{type(e).__name__}: {e}"
            return False

    def clear_now_playing(self):
        """Clear now playing status on Last.fm."""
        self.current_track = None
        self.scrobbled = False
        # Last.fm doesn't have an API to clear now playing,
        # it auto-clears after a few minutes of inactivity

    def check_scrobble(self, position: float, actual_duration: float = 0):
        """Check if we should scrobble based on playback position.

        Args:
            position: Current playback position in seconds
            actual_duration: Actual track duration from player (may differ from track metadata)
        """
        if not self.enabled or not self.current_track or self.scrobbled:
            return

        track = self.current_track
        duration = actual_duration if actual_duration > 0 else track.duration

        # If we still don't have duration, use time-based scrobbling only
        if duration <= 0:
            # Scrobble after 4 minutes of playback (Last.fm minimum is 30 seconds)
            if position >= self.SCROBBLE_MAX_TIME:
                self._scrobble()
            return

        # Check if we've played enough of the track
        played_ratio = position / duration

        if played_ratio >= self.SCROBBLE_THRESHOLD or position >= self.SCROBBLE_MAX_TIME:
            self._scrobble()

    def _scrobble(self) -> bool:
        """Submit scrobble to Last.fm."""
        if not self.enabled or not self.current_track or self.scrobbled:
            return False

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
            return True
        except Exception as e:
            self._last_error = str(e)
            return False

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

    def get_similar_tracks(self, track: Track, limit: int = 20) -> list:
        """Get tracks similar to the given track."""
        if not self.enabled:
            return []

        try:
            lastfm_track = self.network.get_track(track.artist, track.title)
            similar = lastfm_track.get_similar(limit=limit)
            return [
                {"artist": item.item.artist.name, "title": item.item.title}
                for item in similar
            ]
        except Exception:
            return []

    def get_similar_artists(self, artist: str, limit: int = 10) -> list:
        """Get artists similar to the given artist."""
        if not self.enabled:
            return []

        try:
            lastfm_artist = self.network.get_artist(artist)
            similar = lastfm_artist.get_similar(limit=limit)
            return [item.item.name for item in similar]
        except Exception:
            return []

    def get_loved_tracks(self, limit: int = 50) -> list:
        """Get user's loved tracks from Last.fm."""
        if not self.enabled:
            return []

        try:
            user = self.network.get_user(self.network.username)
            loved = user.get_loved_tracks(limit=limit)
            return [
                {"artist": item.track.artist.name, "title": item.track.title}
                for item in loved
            ]
        except Exception:
            return []

    def is_loved(self, track: Track) -> bool:
        """Check if a track is loved on Last.fm."""
        if not self.enabled or not track:
            return False

        try:
            lastfm_track = self.network.get_track(track.artist, track.title)
            return lastfm_track.get_userloved()
        except Exception:
            return False

    def get_top_artists(self, period: str = "3month", limit: int = 20) -> list:
        """Get user's top artists from Last.fm.

        Args:
            period: Time period - overall, 7day, 1month, 3month, 6month, 12month
            limit: Number of artists to return
        """
        if not self.enabled:
            return []

        try:
            user = self.network.get_user(self.network.username)
            top = user.get_top_artists(period=period, limit=limit)
            return [item.item.name for item in top]
        except Exception:
            return []

    def get_track_tags(self, track: Track, limit: int = 3) -> list:
        """Get genre tags for an artist from Last.fm."""
        if not self.enabled or not track.artist:
            return []

        try:
            # Get artist tags instead of track tags - more reliable
            artist_name = track.artist.split(',')[0].strip()  # Use first artist if multiple
            lastfm_artist = self.network.get_artist(artist_name)
            tags = lastfm_artist.get_top_tags(limit=limit)
            # Filter out empty tags and get names
            result = []
            for tag in tags:
                if hasattr(tag, 'item') and hasattr(tag.item, 'name'):
                    name = tag.item.name
                    if name and name.strip():
                        result.append(name)
            return result[:limit]
        except Exception as e:
            self._last_error = str(e)
            return []

    def get_recommendations(self, limit: int = 30) -> list:
        """Get track recommendations based on loved tracks and listening history."""
        if not self.enabled:
            return []

        recommendations = []

        # Get similar tracks from loved tracks
        loved = self.get_loved_tracks(limit=10)
        for track_info in loved[:5]:
            track = Track(
                title=track_info["title"],
                artist=track_info["artist"],
                album="",
                duration=0,
                url="",
                source="lastfm",
            )
            similar = self.get_similar_tracks(track, limit=5)
            for s in similar:
                if s not in recommendations:
                    recommendations.append(s)

        # Get tracks from similar artists
        top_artists = self.get_top_artists(limit=5)
        for artist in top_artists[:3]:
            similar_artists = self.get_similar_artists(artist, limit=3)
            for sim_artist in similar_artists:
                try:
                    lastfm_artist = self.network.get_artist(sim_artist)
                    top_tracks = lastfm_artist.get_top_tracks(limit=3)
                    for item in top_tracks:
                        rec = {"artist": sim_artist, "title": item.item.title}
                        if rec not in recommendations:
                            recommendations.append(rec)
                except Exception:
                    pass

        return recommendations[:limit]
