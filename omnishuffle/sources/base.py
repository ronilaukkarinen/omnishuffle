"""Base class for music sources."""

from abc import ABC, abstractmethod
from typing import List, Optional
from omnishuffle.player import Track


class MusicSource(ABC):
    """Abstract base class for music sources."""

    name: str = "base"

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if this source is properly configured."""
        pass

    @abstractmethod
    def get_playlists(self) -> List[dict]:
        """Get available playlists."""
        pass

    @abstractmethod
    def get_tracks_from_playlist(self, playlist_id: str) -> List[Track]:
        """Get tracks from a playlist."""
        pass

    @abstractmethod
    def get_radio_tracks(self, seed: Optional[str] = None) -> List[Track]:
        """Get radio/recommendation tracks."""
        pass

    @abstractmethod
    def get_stream_url(self, track: Track) -> str:
        """Get the actual stream URL for a track."""
        pass

    def love_track(self, track: Track) -> bool:
        """Mark a track as loved/liked. Returns True if supported."""
        return False

    def ban_track(self, track: Track) -> bool:
        """Ban/dislike a track. Returns True if supported."""
        return False
