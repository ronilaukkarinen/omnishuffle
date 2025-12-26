"""Spotify music source using spotipy and librespot for direct streaming."""

import os
import subprocess
import tempfile
import threading
from typing import List, Optional

from omnishuffle.player import Track
from omnishuffle.sources.base import MusicSource

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False

# Set protobuf implementation before importing librespot
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

try:
    from librespot.core import Session
    from librespot.audio.decoders import AudioQuality, VorbisOnlyAudioQuality
    from librespot.metadata import TrackId
    LIBRESPOT_AVAILABLE = True
except ImportError:
    LIBRESPOT_AVAILABLE = False


class SpotifySource(MusicSource):
    """Spotify source with direct 320kbps streaming via librespot."""

    name = "spotify"

    def __init__(self, config: dict):
        self.config = config
        self.sp: Optional[spotipy.Spotify] = None
        self._librespot_session: Optional[Session] = None
        self._librespot_available = False
        self._init_client()
        self._init_librespot()

    def _init_client(self):
        """Initialize Spotify client."""
        if not SPOTIPY_AVAILABLE:
            return

        client_id = self.config.get("client_id") or os.getenv("SPOTIPY_CLIENT_ID")
        client_secret = self.config.get("client_secret") or os.getenv("SPOTIPY_CLIENT_SECRET")
        redirect_uri = self.config.get("redirect_uri", "http://127.0.0.1:8080")

        if client_id and client_secret:
            try:
                auth_manager = SpotifyOAuth(
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uri=redirect_uri,
                    scope="user-library-read user-library-modify playlist-read-private user-read-playback-state user-modify-playback-state user-top-read streaming",
                    cache_path=os.path.expanduser("~/.config/omnishuffle/spotify_cache"),
                )
                self.sp = spotipy.Spotify(auth_manager=auth_manager)
            except Exception:
                self.sp = None

    def _init_librespot(self):
        """Initialize librespot session for direct streaming."""
        if not LIBRESPOT_AVAILABLE:
            return

        # Try stored credentials first (from previous OAuth)
        creds_file = os.path.expanduser("~/.config/omnishuffle/librespot_creds")
        if os.path.exists(creds_file):
            try:
                self._librespot_session = Session.Builder() \
                    .stored_file(creds_file) \
                    .create()
                self._librespot_available = True
                return
            except Exception:
                pass

        # Get Spotify credentials
        username = self.config.get("username") or os.getenv("SPOTIFY_USERNAME")
        password = self.config.get("password") or os.getenv("SPOTIFY_PASSWORD")

        if not username or not password:
            # Try to read from spotifyd config
            spotifyd_conf = os.path.expanduser("~/.config/spotifyd/spotifyd.conf")
            if os.path.exists(spotifyd_conf):
                try:
                    with open(spotifyd_conf) as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("username"):
                                username = line.split("=", 1)[1].strip().strip('"')
                            elif line.startswith("password"):
                                password = line.split("=", 1)[1].strip().strip('"')
                except Exception:
                    pass

        if username and password:
            try:
                self._librespot_session = Session.Builder() \
                    .user_pass(username, password) \
                    .create()
                self._librespot_available = True
                # Save credentials for next time
                try:
                    self._librespot_session.stored(creds_file)
                except Exception:
                    pass
            except Exception:
                self._librespot_session = None
                self._librespot_available = False

    def get_audio_stream(self, track: Track) -> Optional[bytes]:
        """Get raw audio stream for a Spotify track via librespot."""
        if not self._librespot_available or not track.track_id:
            return None

        try:
            track_id = TrackId.from_base62(track.track_id)
            stream = self._librespot_session.content_feeder().load(
                track_id,
                VorbisOnlyAudioQuality(AudioQuality.VERY_HIGH),
                False,
                None
            )
            # Read all audio data
            return stream.input_stream.stream().read()
        except Exception:
            return None

    def get_stream_file(self, track: Track) -> Optional[str]:
        """Get audio stream as a temporary file path."""
        audio_data = self.get_audio_stream(track)
        if not audio_data:
            return None

        try:
            # Create temp file with .ogg extension (Vorbis)
            fd, path = tempfile.mkstemp(suffix=".ogg", prefix="omnishuffle_")
            with os.fdopen(fd, 'wb') as f:
                f.write(audio_data)
            return path
        except Exception:
            return None

    @property
    def has_direct_streaming(self) -> bool:
        """Check if direct 320kbps streaming is available."""
        return self._librespot_available

    def is_configured(self) -> bool:
        """Check if Spotify is configured."""
        if not self.sp:
            return False
        try:
            self.sp.current_user()
            return True
        except Exception:
            return False

    def get_playlists(self) -> List[dict]:
        """Get user's playlists."""
        if not self.sp:
            return []

        playlists = []
        results = self.sp.current_user_playlists(limit=50)
        while results:
            for item in results["items"]:
                playlists.append({
                    "id": item["id"],
                    "name": item["name"],
                    "track_count": item["tracks"]["total"],
                })
            if results["next"]:
                results = self.sp.next(results)
            else:
                break
        return playlists

    def get_tracks_from_playlist(self, playlist_id: str) -> List[Track]:
        """Get tracks from a Spotify playlist."""
        if not self.sp:
            return []

        tracks = []
        results = self.sp.playlist_tracks(playlist_id)
        while results:
            for item in results["items"]:
                track_data = item.get("track")
                if not track_data:
                    continue

                track = Track(
                    title=track_data["name"],
                    artist=", ".join(a["name"] for a in track_data["artists"]),
                    album=track_data["album"]["name"],
                    duration=track_data["duration_ms"] // 1000,
                    url="",  # Played via Spotify Connect
                    source="spotify",
                    artwork_url=track_data["album"]["images"][0]["url"] if track_data["album"]["images"] else None,
                    track_id=track_data["id"],
                )
                tracks.append(track)

            if results["next"]:
                results = self.sp.next(results)
            else:
                break
        return tracks

    def get_liked_tracks(self, limit: int = 50) -> List[Track]:
        """Get user's liked/saved tracks."""
        if not self.sp:
            return []

        tracks = []
        try:
            results = self.sp.current_user_saved_tracks(limit=min(limit, 50))
            while results and len(tracks) < limit:
                for item in results["items"]:
                    track_data = item.get("track")
                    if not track_data:
                        continue

                    track = Track(
                        title=track_data["name"],
                        artist=", ".join(a["name"] for a in track_data["artists"]),
                        album=track_data["album"]["name"],
                        duration=track_data["duration_ms"] // 1000,
                        url="",
                        source="spotify",
                        artwork_url=track_data["album"]["images"][0]["url"] if track_data["album"]["images"] else None,
                        track_id=track_data["id"],
                    )
                    tracks.append(track)

                if results["next"] and len(tracks) < limit:
                    results = self.sp.next(results)
                else:
                    break
        except Exception:
            pass
        return tracks[:limit]

    def get_radio_tracks(self, seed: Optional[str] = None) -> List[Track]:
        """Get recommendations based on seed."""
        if not self.sp:
            return []

        try:
            # Get user's top tracks as seeds if no seed provided
            if not seed:
                top_tracks = self.sp.current_user_top_tracks(limit=5, time_range="short_term")
                seed_tracks = [t["id"] for t in top_tracks["items"][:5]]
            else:
                # Search for the seed
                results = self.sp.search(q=seed, type="track", limit=1)
                if results["tracks"]["items"]:
                    seed_tracks = [results["tracks"]["items"][0]["id"]]
                else:
                    return []

            recommendations = self.sp.recommendations(seed_tracks=seed_tracks[:5], limit=50)
            tracks = []
            for track_data in recommendations["tracks"]:
                track = Track(
                    title=track_data["name"],
                    artist=", ".join(a["name"] for a in track_data["artists"]),
                    album=track_data["album"]["name"],
                    duration=track_data["duration_ms"] // 1000,
                    url="",
                    source="spotify",
                    artwork_url=track_data["album"]["images"][0]["url"] if track_data["album"]["images"] else None,
                    track_id=track_data["id"],
                )
                tracks.append(track)
            return tracks
        except Exception:
            return []

    def get_stream_url(self, track: Track) -> str:
        """Get stream URL - Spotify uses Connect, returns empty."""
        return ""

    def love_track(self, track: Track) -> bool:
        """Save track to library."""
        if not self.sp or not track.track_id:
            return False
        try:
            self.sp.current_user_saved_tracks_add([track.track_id])
            return True
        except Exception:
            return False

    # Spotify Connect methods for direct playback

    def get_devices(self) -> List[dict]:
        """Get available Spotify Connect devices."""
        if not self.sp:
            return []
        try:
            result = self.sp.devices()
            return result.get("devices", [])
        except Exception:
            return []

    def get_connect_device(self) -> Optional[dict]:
        """Find a suitable Spotify Connect device (prefer librespot/spotifyd)."""
        devices = self.get_devices()
        # Prefer librespot/spotifyd devices
        for device in devices:
            name = device.get("name", "").lower()
            if "librespot" in name or "spotifyd" in name or "omnishuffle" in name:
                return device
        # Fall back to any active device
        for device in devices:
            if device.get("is_active"):
                return device
        # Fall back to first available device
        return devices[0] if devices else None

    def play_track_on_device(self, track: Track, device_id: str) -> bool:
        """Play a track on a Spotify Connect device."""
        if not self.sp or not track.track_id:
            return False
        try:
            uri = f"spotify:track:{track.track_id}"
            self.sp.start_playback(device_id=device_id, uris=[uri])
            return True
        except Exception:
            return False

    def get_playback_state(self) -> Optional[dict]:
        """Get current playback state."""
        if not self.sp:
            return None
        try:
            return self.sp.current_playback()
        except Exception:
            return None

    def pause_playback(self, device_id: Optional[str] = None) -> bool:
        """Pause playback."""
        if not self.sp:
            return False
        try:
            self.sp.pause_playback(device_id=device_id)
            return True
        except Exception:
            return False

    def resume_playback(self, device_id: Optional[str] = None) -> bool:
        """Resume playback."""
        if not self.sp:
            return False
        try:
            self.sp.start_playback(device_id=device_id)
            return True
        except Exception:
            return False

    def seek_playback(self, position_ms: int, device_id: Optional[str] = None) -> bool:
        """Seek to position."""
        if not self.sp:
            return False
        try:
            self.sp.seek_track(position_ms, device_id=device_id)
            return True
        except Exception:
            return False

    def set_volume(self, volume_percent: int, device_id: Optional[str] = None) -> bool:
        """Set volume (0-100)."""
        if not self.sp:
            return False
        try:
            self.sp.volume(volume_percent, device_id=device_id)
            return True
        except Exception:
            return False

    def transfer_playback(self, device_id: str) -> bool:
        """Transfer playback to a device."""
        if not self.sp:
            return False
        try:
            self.sp.transfer_playback(device_id=device_id, force_play=False)
            return True
        except Exception:
            return False
