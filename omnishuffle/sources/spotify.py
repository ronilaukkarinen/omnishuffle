"""Spotify music source using spotipy."""

import os
import subprocess
from typing import List, Optional

from omnishuffle.player import Track
from omnishuffle.sources.base import MusicSource

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False


class SpotifySource(MusicSource):
    """Spotify source - uses yt-dlp to find matching YouTube streams."""

    name = "spotify"

    def __init__(self, config: dict):
        self.config = config
        self.sp: Optional[spotipy.Spotify] = None
        self._init_client()

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
                    scope="user-library-read playlist-read-private user-read-playback-state",
                    cache_path=os.path.expanduser("~/.config/omnishuffle/spotify_cache"),
                )
                self.sp = spotipy.Spotify(auth_manager=auth_manager)
            except Exception:
                self.sp = None

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
                    url="",  # Will be resolved via YouTube
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
        """Get YouTube URL for a Spotify track."""
        search_query = f"ytsearch1:{track.artist} - {track.title}"
        return search_query

    def love_track(self, track: Track) -> bool:
        """Save track to library."""
        if not self.sp or not track.track_id:
            return False
        try:
            self.sp.current_user_saved_tracks_add([track.track_id])
            return True
        except Exception:
            return False
