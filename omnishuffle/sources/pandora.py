"""Pandora music source using pydora with Tor proxy support."""

import os
import socket
import subprocess
import time
import atexit
import tempfile
from typing import List, Optional
from pathlib import Path

from omnishuffle.player import Track
from omnishuffle.sources.base import MusicSource

# Custom torrc for US exit nodes only
TORRC_CONTENT = """ExitNodes {us}
StrictNodes 1
CircuitBuildTimeout 5
NumEntryGuards 6
KeepalivePeriod 60
NewCircuitPeriod 15
SOCKSPort 9050
"""

try:
    from pandora.clientbuilder import SettingsDictBuilder
    PYDORA_AVAILABLE = True
except ImportError:
    PYDORA_AVAILABLE = False

# Partner keys for Pandora API (iOS keys - more reliable)
PANDORA_PARTNER = {
    "DECRYPTION_KEY": "20zE1E47BE57$51",
    "ENCRYPTION_KEY": "721^702xC5+E",
    "PARTNER_USER": "iphone",
    "PARTNER_PASSWORD": "P2E4FC0EAD3*878N92B2CDp34I0B1@388137C",
    "DEVICE": "IP01",
}


class PandoraSource(MusicSource):
    """Pandora source with Tor/SOCKS5 proxy support."""

    name = "pandora"
    _tor_process: Optional[subprocess.Popen] = None
    _torrc_file: Optional[str] = None

    def __init__(self, config: dict):
        self.config = config
        self.client = None
        self.stations: List[dict] = []
        self.current_station = None
        self.error_message: Optional[str] = None
        self._init_client()

    @classmethod
    def _is_tor_running(cls, port: int = 9050) -> bool:
        """Check if Tor is running on the specified port."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0
        except Exception:
            return False

    @classmethod
    def _start_tor(cls) -> bool:
        """Start Tor daemon with US exit nodes."""
        if cls._is_tor_running():
            return True

        try:
            # Create custom torrc with US exit nodes
            torrc_path = Path(tempfile.gettempdir()) / "omnishuffle_torrc"
            torrc_path.write_text(TORRC_CONTENT)
            cls._torrc_file = str(torrc_path)

            # Start Tor with custom config
            cls._tor_process = subprocess.Popen(
                ['tor', '-f', str(torrc_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Register cleanup
            atexit.register(cls._stop_tor)

            # Wait for Tor to start (up to 30 seconds)
            for _ in range(30):
                if cls._is_tor_running():
                    return True
                time.sleep(1)

            return False
        except FileNotFoundError:
            return False
        except Exception:
            return False

    @classmethod
    def _stop_tor(cls):
        """Stop Tor daemon if we started it."""
        if cls._tor_process:
            cls._tor_process.terminate()
            cls._tor_process = None
        if cls._torrc_file:
            try:
                Path(cls._torrc_file).unlink(missing_ok=True)
            except Exception:
                pass
            cls._torrc_file = None

    def _init_client(self):
        """Initialize Pandora client with optional proxy."""
        if not PYDORA_AVAILABLE:
            self.error_message = "pydora not installed"
            return

        email = self.config.get("email") or os.getenv("PANDORA_EMAIL")
        password = self.config.get("password") or os.getenv("PANDORA_PASSWORD")
        proxy = self.config.get("proxy")  # e.g., "socks5://127.0.0.1:9050"

        if not email or not password:
            self.error_message = "email/password not set"
            return

        try:
            # Start Tor if proxy is configured
            if proxy and "9050" in proxy:
                if not self._start_tor():
                    self.error_message = "could not start Tor"
                    return

            # Set up proxy if configured
            if proxy:
                os.environ["HTTP_PROXY"] = proxy
                os.environ["HTTPS_PROXY"] = proxy
                os.environ["ALL_PROXY"] = proxy

            self.client = SettingsDictBuilder(PANDORA_PARTNER).build()
            self.client.login(email, password)
        except Exception as e:
            # Use sentence case for error messages
            msg = str(e)
            self.error_message = msg[0].lower() + msg[1:] if msg else "unknown error"
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
