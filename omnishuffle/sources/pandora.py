"""Pandora music source using pydora with Tor proxy support."""

import os
import socket
import subprocess
import time
import atexit
import tempfile
import urllib.request
from typing import List, Optional
from pathlib import Path

from omnishuffle.player import Track
from omnishuffle.sources.base import MusicSource

# Custom torrc for US exit nodes only
TORRC_CONTENT = """ExitNodes {US}
StrictNodes 1
CircuitBuildTimeout 10
NumEntryGuards 6
KeepalivePeriod 60
NewCircuitPeriod 10
SOCKSPort 9050
DataDirectory /tmp/omnishuffle_tor_data
ControlPort 9051
"""

try:
    from pandora.clientbuilder import SettingsDictBuilder
    PYDORA_AVAILABLE = True
except ImportError:
    PYDORA_AVAILABLE = False

# Partner keys for Pandora API (Android keys from pianobar)
PANDORA_PARTNER = {
    "DECRYPTION_KEY": "R=U!LH$O2B#",
    "ENCRYPTION_KEY": "6#26FRL$ZWD",
    "PARTNER_USER": "android",
    "PARTNER_PASSWORD": "AC7IBG09A3DTSYM4R41UJWL07VLN8JI7",
    "DEVICE": "android-generic",
}


class PandoraSource(MusicSource):
    """Pandora source with Tor/SOCKS5 proxy support."""

    name = "pandora"
    _tor_process: Optional[subprocess.Popen] = None
    _torrc_file: Optional[str] = None
    _proxy: Optional[str] = None

    def __init__(self, config: dict):
        self.config = config
        self.client = None
        self.stations: List[dict] = []
        self.current_station = None
        self.error_message: Optional[str] = None
        self._init_client()

    def _set_proxy(self):
        """Set proxy env vars for Pandora API calls."""
        if self._proxy:
            os.environ["HTTP_PROXY"] = self._proxy
            os.environ["HTTPS_PROXY"] = self._proxy
            os.environ["ALL_PROXY"] = self._proxy

    def _clear_proxy(self):
        """Clear proxy env vars after Pandora API calls."""
        for var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
            os.environ.pop(var, None)

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
    def _stop_existing_tor(cls):
        """Stop any existing Tor processes."""
        # Stop systemd service
        subprocess.run(
            ['sudo', 'systemctl', 'stop', 'tor'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Kill any remaining tor processes
        subprocess.run(
            ['pkill', '-9', 'tor'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for port to be released
        for _ in range(10):
            if not cls._is_tor_running():
                return
            time.sleep(0.5)

    @classmethod
    def _verify_us_exit(cls) -> bool:
        """Verify we have a US exit node by checking IP geolocation."""
        try:
            import httpx
            # Get exit IP via ipify (Tor-friendly)
            with httpx.Client(proxy="socks5://127.0.0.1:9050", timeout=10) as client:
                response = client.get("https://api.ipify.org")
                exit_ip = response.text.strip()

            # Check country via direct request (most geo services block Tor)
            with httpx.Client(timeout=10) as client:
                response = client.get(f"https://ipinfo.io/{exit_ip}/country")
                country = response.text.strip()
                return country == "US"
        except Exception:
            # If we can't verify, assume it's OK (torrc specifies US anyway)
            return True

    @classmethod
    def _request_new_circuit(cls):
        """Request a new Tor circuit via control port."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", 9051))
            s.send(b"AUTHENTICATE\r\n")
            s.recv(1024)
            s.send(b"SIGNAL NEWNYM\r\n")
            s.recv(1024)
            s.close()
            time.sleep(2)  # Wait for new circuit
        except Exception:
            pass

    @classmethod
    def _start_tor(cls) -> bool:
        """Start Tor daemon with US exit nodes."""
        # If Tor is already running, just use it
        if cls._is_tor_running():
            return True

        try:
            # Create data directory
            data_dir = Path("/tmp/omnishuffle_tor_data")
            data_dir.mkdir(exist_ok=True)

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
                    # Verify US exit, retry with new circuit if not
                    for attempt in range(3):
                        if cls._verify_us_exit():
                            return True
                        cls._request_new_circuit()
                    return True  # Give up verifying, try anyway
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

            # Store proxy for later API calls
            PandoraSource._proxy = proxy

            # Set up proxy for login
            self._set_proxy()

            # Retry login with different circuits if geo-blocked
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    self.client = SettingsDictBuilder(PANDORA_PARTNER).build()
                    self.client.login(email, password)
                    return  # Success
                except Exception as e:
                    msg = str(e).lower()
                    if "country" in msg or "geo" in msg or "not available" in msg:
                        # Geo-blocked - try new circuit
                        if attempt < max_retries - 1:
                            self._request_new_circuit()
                            continue
                    raise  # Re-raise for other errors or final attempt
        except Exception as e:
            # Use sentence case for error messages
            msg = str(e)
            self.error_message = msg.lower() if msg else "unknown error"
            self.client = None
        finally:
            # Always clear proxy after init so other services work
            self._clear_proxy()

    def is_configured(self) -> bool:
        """Check if Pandora is configured."""
        return self.client is not None

    def get_playlists(self) -> List[dict]:
        """Get Pandora stations (treated as playlists)."""
        if not self.client:
            return []

        try:
            self._set_proxy()
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
        finally:
            self._clear_proxy()

    def get_tracks_from_playlist(self, playlist_id: str) -> List[Track]:
        """Get tracks from a Pandora station."""
        return self.get_radio_tracks(playlist_id)

    def get_radio_tracks(self, seed: Optional[str] = None) -> List[Track]:
        """Get tracks from Pandora stations using QuickMix (Shuffle)."""
        if not self.client:
            return []

        try:
            self._set_proxy()
            stations = self.client.get_station_list()
            if not stations:
                return []

            # If seed specified, use only that station
            if seed:
                for s in stations:
                    if s.id == seed or s.name.lower() == seed.lower():
                        stations = [s]
                        break
                quickmix_station = stations[0] if stations else None
            else:
                # Find the QuickMix/Shuffle station (has isQuickMix=true)
                quickmix_station = None
                for s in stations:
                    if getattr(s, 'is_quickmix', False) or getattr(s, 'isQuickMix', False):
                        quickmix_station = s
                        break
                    # Also check by name as fallback
                    if s.name.lower() in ('quickmix', 'shuffle'):
                        quickmix_station = s
                        break

            tracks = []

            if quickmix_station:
                # Use actual QuickMix station - Pandora mixes from all selected stations server-side
                self.current_station = quickmix_station
                # Fetch multiple playlists for variety (~4 tracks each)
                for _ in range(5):
                    try:
                        playlist = quickmix_station.get_playlist()
                        for song in playlist:
                            if not hasattr(song, 'song_name') or not song.song_name:
                                continue
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
                    except Exception:
                        pass
            else:
                # Fallback: fetch from individual stations if no QuickMix found
                import random
                random.shuffle(stations)
                for station in stations[:20]:
                    try:
                        self.current_station = station
                        playlist = station.get_playlist()
                        for song in playlist:
                            if not hasattr(song, 'song_name') or not song.song_name:
                                continue
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
                    except Exception:
                        continue

            return tracks
        except Exception:
            return []
        finally:
            self._clear_proxy()

    def get_stream_url(self, track: Track) -> str:
        """Pandora tracks already have direct URLs."""
        return track.url

    def love_track(self, track: Track) -> bool:
        """Thumbs up a track."""
        if not self.client or not track.track_id:
            return False
        try:
            self._set_proxy()
            # pydora uses track tokens for feedback
            if self.current_station:
                self.current_station.add_feedback(track.track_id, True)
                return True
        except Exception:
            pass
        finally:
            self._clear_proxy()
        return False

    def ban_track(self, track: Track) -> bool:
        """Thumbs down a track."""
        if not self.client or not track.track_id:
            return False
        try:
            self._set_proxy()
            if self.current_station:
                self.current_station.add_feedback(track.track_id, False)
                return True
        except Exception:
            pass
        finally:
            self._clear_proxy()
        return False

    def get_more_tracks(self) -> List[Track]:
        """Get more tracks from current station."""
        if not self.current_station:
            return []
        return self.get_radio_tracks(self.current_station.id)
