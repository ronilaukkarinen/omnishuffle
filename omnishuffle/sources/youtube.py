"""YouTube Music source using ytmusicapi and yt-dlp."""

import os
import json
import subprocess
from typing import List, Optional

from omnishuffle.player import Track
from omnishuffle.sources.base import MusicSource

try:
    from ytmusicapi import YTMusic
    YTMUSIC_AVAILABLE = True
except ImportError:
    YTMUSIC_AVAILABLE = False


class YouTubeSource(MusicSource):
    """YouTube Music source."""

    name = "youtube"

    def __init__(self, config: dict):
        self.config = config
        self.yt: Optional[YTMusic] = None
        self._init_client()

    def _init_client(self):
        """Initialize YouTube Music client."""
        if not YTMUSIC_AVAILABLE:
            return

        auth_file = self.config.get("auth_file") or os.path.expanduser(
            "~/.config/omnishuffle/ytmusic_auth.json"
        )

        try:
            if os.path.exists(auth_file):
                self.yt = YTMusic(auth_file)
            else:
                # Use without auth (limited features)
                self.yt = YTMusic()
        except Exception:
            self.yt = YTMusic()  # Fallback to unauthenticated

    def is_configured(self) -> bool:
        """YouTube works without auth, so always configured if library available."""
        return YTMUSIC_AVAILABLE

    def get_playlists(self) -> List[dict]:
        """Get user's playlists (requires auth)."""
        if not self.yt:
            return []

        try:
            playlists = self.yt.get_library_playlists(limit=50)
            return [
                {
                    "id": p["playlistId"],
                    "name": p["title"],
                    "track_count": p.get("count", 0),
                }
                for p in playlists
            ]
        except Exception:
            return []

    def get_tracks_from_playlist(self, playlist_id: str) -> List[Track]:
        """Get tracks from a YouTube Music playlist."""
        if not self.yt:
            return []

        try:
            playlist = self.yt.get_playlist(playlist_id, limit=100)
            tracks = []
            for item in playlist.get("tracks", []):
                if not item.get("videoId"):
                    continue

                artists = item.get("artists", [])
                artist_name = ", ".join(a["name"] for a in artists) if artists else "Unknown"

                track = Track(
                    title=item.get("title", "Unknown"),
                    artist=artist_name,
                    album=item.get("album", {}).get("name", "") if item.get("album") else "",
                    duration=item.get("duration_seconds", 0) or 0,
                    url=f"https://music.youtube.com/watch?v={item['videoId']}",
                    source="youtube",
                    artwork_url=item.get("thumbnails", [{}])[-1].get("url"),
                    track_id=item["videoId"],
                )
                tracks.append(track)
            return tracks
        except Exception:
            return []

    def get_radio_tracks(self, seed: Optional[str] = None) -> List[Track]:
        """Get radio/recommendations based on a search or video."""
        if not self.yt:
            return []

        try:
            if seed:
                # Search for the seed
                results = self.yt.search(seed, filter="songs", limit=1)
                if results:
                    video_id = results[0].get("videoId")
                    if video_id:
                        # Get radio based on this song
                        radio = self.yt.get_watch_playlist(videoId=video_id, limit=50)
                        return self._parse_watch_playlist(radio)

            # Fallback to home recommendations
            home = self.yt.get_home(limit=3)
            tracks = []
            for section in home:
                for item in section.get("contents", [])[:10]:
                    if item.get("videoId"):
                        artists = item.get("artists", [])
                        artist_name = ", ".join(a["name"] for a in artists) if artists else "Unknown"
                        track = Track(
                            title=item.get("title", "Unknown"),
                            artist=artist_name,
                            album="",
                            duration=0,
                            url=f"https://music.youtube.com/watch?v={item['videoId']}",
                            source="youtube",
                            artwork_url=item.get("thumbnails", [{}])[-1].get("url"),
                            track_id=item["videoId"],
                        )
                        tracks.append(track)
            return tracks
        except Exception:
            return []

    def _parse_watch_playlist(self, radio: dict) -> List[Track]:
        """Parse a watch playlist response."""
        tracks = []
        for item in radio.get("tracks", []):
            if not item.get("videoId"):
                continue

            artists = item.get("artists", [])
            artist_name = ", ".join(a["name"] for a in artists) if artists else "Unknown"

            track = Track(
                title=item.get("title", "Unknown"),
                artist=artist_name,
                album=item.get("album", {}).get("name", "") if item.get("album") else "",
                duration=item.get("length_seconds", 0) or 0,
                url=f"https://music.youtube.com/watch?v={item['videoId']}",
                source="youtube",
                artwork_url=item.get("thumbnail", [{}])[-1].get("url") if item.get("thumbnail") else None,
                track_id=item["videoId"],
            )
            tracks.append(track)
        return tracks

    def get_stream_url(self, track: Track) -> str:
        """Get the YouTube URL (mpv/yt-dlp will handle it)."""
        return track.url

    def love_track(self, track: Track) -> bool:
        """Like a track on YouTube Music."""
        if not self.yt or not track.track_id:
            return False
        try:
            self.yt.rate_song(track.track_id, "LIKE")
            return True
        except Exception:
            return False

    def search(self, query: str, limit: int = 20) -> List[Track]:
        """Search for tracks."""
        if not self.yt:
            return []

        try:
            results = self.yt.search(query, filter="songs", limit=limit)
            tracks = []
            for item in results:
                if not item.get("videoId"):
                    continue

                artists = item.get("artists", [])
                artist_name = ", ".join(a["name"] for a in artists) if artists else "Unknown"

                track = Track(
                    title=item.get("title", "Unknown"),
                    artist=artist_name,
                    album=item.get("album", {}).get("name", "") if item.get("album") else "",
                    duration=item.get("duration_seconds", 0) or 0,
                    url=f"https://music.youtube.com/watch?v={item['videoId']}",
                    source="youtube",
                    artwork_url=item.get("thumbnails", [{}])[-1].get("url"),
                    track_id=item["videoId"],
                )
                tracks.append(track)
            return tracks
        except Exception:
            return []
