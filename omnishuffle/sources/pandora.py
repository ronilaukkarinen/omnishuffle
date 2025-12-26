"""Pandora music source using pydora with Tor proxy support."""

import os
from typing import List, Optional

from omnishuffle.player import Track
from omnishuffle.sources.base import MusicSource

try:
    from pydora.api import Pandora
    from pydora.utils import PandoraConfig
    PYDORA_AVAILABLE = True
except ImportError:
    PYDORA_AVAILABLE = False


class PandoraSource(MusicSource):
    """Pandora source with Tor/SOCKS5 proxy support."""

    name = "pandora"

    def __init__(self, config: dict):
        self.config = config
        self.client: Optional[Pandora] = None
        self.stations: List[dict] = []
        self.current_station = None
        self._init_client()

    def _init_client(self):
        """Initialize Pandora client with optional proxy."""
        if not PYDORA_AVAILABLE:
            return

        email = self.config.get("email") or os.getenv("PANDORA_EMAIL")
        password = self.config.get("password") or os.getenv("PANDORA_PASSWORD")
        proxy = self.config.get("proxy")  # e.g., "socks5://127.0.0.1:9050"

        if not email or not password:
            return

        try:
            # Set up proxy if configured (for Tor)
            if proxy:
                os.environ["HTTP_PROXY"] = proxy
                os.environ["HTTPS_PROXY"] = proxy

            self.client = Pandora()
            self.client.login(email, password)
        except Exception:
            self.client = None

    def is_configured(self) -> bool:
        """Check if Pandora is configured."""
        return self.client is not None

    def get_playlists(self) -> List[dict]:
        """Get Pandora stations (treated as playlists)."""
        if not self.client:
            return []

        try:
            stations = self.client.get_station_list()
            self.stations = [
                {
                    "id": s.id,
                    "name": s.name,
                    "track_count": 0,  # Pandora doesn't expose this
                }
                for s in stations
            ]
            return self.stations
        except Exception:
            return []

    def get_tracks_from_playlist(self, playlist_id: str) -> List[Track]:
        """Get tracks from a Pandora station."""
        return self.get_radio_tracks(playlist_id)

    def get_radio_tracks(self, seed: Optional[str] = None) -> List[Track]:
        """Get tracks from a Pandora station."""
        if not self.client:
            return []

        try:
            # Find station by ID or name
            station = None
            if seed:
                stations = self.client.get_station_list()
                for s in stations:
                    if s.id == seed or s.name.lower() == seed.lower():
                        station = s
                        break

            if not station:
                # Use first station
                stations = self.client.get_station_list()
                if stations:
                    station = stations[0]
                else:
                    return []

            self.current_station = station
            playlist = station.get_playlist()

            tracks = []
            for song in playlist:
                track = Track(
                    title=song.song_name,
                    artist=song.artist_name,
                    album=song.album_name,
                    duration=song.track_length or 0,
                    url=song.audio_url,
                    source="pandora",
                    artwork_url=song.album_art_url,
                    track_id=song.track_token,
                )
                tracks.append(track)
            return tracks
        except Exception:
            return []

    def get_stream_url(self, track: Track) -> str:
        """Pandora tracks already have direct URLs."""
        return track.url

    def love_track(self, track: Track) -> bool:
        """Thumbs up a track."""
        if not self.client or not track.track_id:
            return False
        try:
            # pydora uses track tokens for feedback
            if self.current_station:
                self.current_station.add_feedback(track.track_id, True)
                return True
        except Exception:
            pass
        return False

    def ban_track(self, track: Track) -> bool:
        """Thumbs down a track."""
        if not self.client or not track.track_id:
            return False
        try:
            if self.current_station:
                self.current_station.add_feedback(track.track_id, False)
                return True
        except Exception:
            pass
        return False

    def get_more_tracks(self) -> List[Track]:
        """Get more tracks from current station."""
        if not self.current_station:
            return []
        return self.get_radio_tracks(self.current_station.id)
