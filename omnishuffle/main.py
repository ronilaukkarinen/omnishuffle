#!/usr/bin/env python3
"""OmniShuffle - Unified music shuffler with pianobar-style controls."""

import sys
import random
import threading
import time
from typing import List, Optional

try:
    import readchar
except ImportError:
    print("Missing dependency: pip install readchar")
    sys.exit(1)

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner
from rich.layout import Layout
from rich import box

from omnishuffle.config import load_config, get_config_dir, add_banned, is_banned
from omnishuffle.player import Player, Track
from omnishuffle.sources import SpotifySource, PandoraSource, YouTubeSource, MusicSource
from omnishuffle.scrobbler import Scrobbler

try:
    import pylast
    PYLAST_AVAILABLE = True
except ImportError:
    PYLAST_AVAILABLE = False


console = Console()

# EQ-style animation (vertical bars)
SPINNER_FRAMES = ["▂▄", "▄▆", "▆█", "█▆", "▆▄", "▄▂", "▂▆", "▆▂"]


HELP_TEXT = """
[bold magenta]OmniShuffle Controls[/bold magenta]

[magenta]n[/magenta]  Next track          [magenta]p[/magenta]  Pause/Resume
[magenta]+[/magenta]  Love track          [magenta]-[/magenta]  Ban track (Pandora)
[magenta]([/magenta]  Volume down         [magenta])[/magenta]  Volume up
[magenta]s[/magenta]  Switch station      [magenta]S[/magenta]  Shuffle sources
[magenta]l[/magenta]  Refresh Last.fm     [magenta]i[/magenta]  Track info
[magenta]h[/magenta]  Show help           [magenta]q[/magenta]  Quit
"""

# Brand colors for services
SOURCE_COLORS = {
    "spotify": "#1DB954",   # Spotify green
    "pandora": "#3668FF",   # Pandora blue
    "youtube": "#FF0000",   # YouTube red
}


class OmniShuffle:
    """Main application class."""

    def __init__(self):
        self.config = load_config()
        self.player = Player()
        self.sources: List[MusicSource] = []
        self.queue: List[Track] = []
        self.history: List[Track] = []
        self.current_track: Optional[Track] = None
        self.running = False
        self.paused = False
        self.spinner_idx = 0
        self.status_thread: Optional[threading.Thread] = None
        self.status_lock = threading.Lock()
        self.scrobbler: Optional[Scrobbler] = None
        self.current_genres: List[str] = []
        self.current_loved: bool = False
        self.current_scrobbled: bool = False  # Track if current song was scrobbled
        self._playing_next = False  # Guard against concurrent play_next calls
        self._current_position: float = 0.0  # Updated by player callback
        self._status_first_print = True  # Reset on track change

        self._init_sources()
        self._init_scrobbler()
        self._setup_callbacks()

    def _clear_status(self):
        """Clear the status lines and reset for fresh print."""
        # Clear current line and line above (2-line status)
        sys.stdout.write("\033[2K\033[A\033[2K\r")
        sys.stdout.flush()
        self._status_first_print = True

    def _format_time(self, seconds: float) -> str:
        """Format seconds as M:SS."""
        mins = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{mins}:{secs:02d}"

    def _get_progress_bar(self, position: float, duration: float, width: int = 24) -> str:
        """Generate a thin modern progress bar."""
        if duration <= 0:
            return "─" * width
        ratio = min(position / duration, 1.0)
        filled = int(width * ratio)
        # Thin line style: ━ (filled) ╸ (position) ─ (empty)
        if filled >= width:
            return "━" * width
        if filled == 0:
            return "╺" + "─" * (width - 1)
        return "━" * filled + "╸" + "─" * (width - filled - 1)

    def _get_status_line(self) -> str:
        """Generate the status line with spinner and colors."""
        if not self.current_track:
            return "\033[2m  No track playing\033[0m\n"

        track = self.current_track

        # ANSI color codes
        colors = {
            "spotify": "\033[38;2;29;185;84m",   # Green
            "pandora": "\033[38;2;54;104;255m",  # Blue
            "youtube": "\033[38;2;255;0;0m",     # Red
        }
        reset = "\033[0m"
        bold = "\033[1m"
        dim = "\033[2m"
        white = "\033[97m"

        color = colors.get(track.source, white)

        # Spinner
        if self.paused:
            spinner = "⏸"
        else:
            spinner = SPINNER_FRAMES[self.spinner_idx % len(SPINNER_FRAMES)]

        # Time - use stored position from observer
        position = self._current_position
        duration = self.player.duration or 0
        progress_bar = self._get_progress_bar(position, duration)
        time_current = self._format_time(position)
        time_total = self._format_time(duration)

        # Quality info
        bitrate = self.player.audio_bitrate
        codec = self.player.audio_codec
        if self.player.is_spotify_direct:
            quality = f"{bitrate}kbps {codec} ⚡"
        elif bitrate and codec:
            quality = f"{bitrate}kbps {codec}"
        else:
            quality = ""

        # Icons
        heart = " \033[91m♥\033[0m" if self.current_loved else ""
        scrobbled = " \033[32m✓\033[0m" if self.current_scrobbled else ""

        # Genres
        genres = f"  \033[38;2;140;140;140m({', '.join(self.current_genres[:2])}){reset}" if self.current_genres else ""

        # Line 1: Track info
        line1 = (
            f"{bold}{color}{spinner}{reset} "
            f"{color}[{track.source.upper()}]{reset} "
            f"{track.artist}{dim} - {reset}{bold}{white}{track.title}{reset}"
            f"{heart}{scrobbled}{genres}"
        )

        # Line 2: Progress
        line2 = (
            f"{color}{progress_bar}{reset} {white}{time_current}{dim}/{time_total}{reset}"
        )
        if quality:
            line2 += f"  {quality}"
        line2 += f"  {dim}vol {self.player.volume}%{reset}"

        return f"{line1}\n{line2}"

    def _status_updater(self):
        """Background thread to update status line."""
        while self.running:
            self.spinner_idx += 1

            if self.current_track:
                # Update position from player
                self._current_position = self.player.position

                status = self._get_status_line()

                # Move to start, clear line, print line1, newline, clear line, print line2
                if not self._status_first_print:
                    sys.stdout.write("\033[A")  # Move up 1 line
                sys.stdout.write(f"\r\033[K{status}\033[K")
                sys.stdout.flush()
                self._status_first_print = False

            # Check for Spotify Connect track end (local timer doesn't know when track ends)
            if self.current_track and self.player.is_spotify_connect and not self.paused:
                dur = self.player.duration
                if dur > 0 and self._current_position >= dur - 1:
                    self._on_track_end()
                    continue

            # Scrobble check
            if self.scrobbler and self.scrobbler.enabled and self.current_track and not self.paused:
                pos = self._current_position
                dur = self.player.duration
                if pos > 0:
                    self.scrobbler.check_scrobble(pos, dur)
                    if self.scrobbler.scrobbled and not self.current_scrobbled:
                        self.current_scrobbled = True

            time.sleep(0.1)

    def _prompt_spotify_activation(self, src):
        """Prompt user to activate Spotify Connect device."""
        console.print("[yellow]![/yellow] Spotify: Open phone → Spotify → Devices → Select 'OmniShuffle'")
        # Don't wait - continue with other sources, Spotify tracks will be skipped

    def _init_sources(self):
        """Initialize enabled music sources."""
        enabled = self.config.get("general", {}).get("sources", [])

        if "spotify" in enabled:
            src = SpotifySource(self.config.get("spotify", {}))
            if src.is_configured():
                self.sources.append(src)
                # Set up Spotify source for player
                self.player.set_spotify_source(src)
                # Check streaming method
                if src.has_direct_streaming:
                    console.print("[green]✓[/green] Spotify connected (320kbps via librespot)")
                else:
                    device = src.get_connect_device()
                    if device:
                        console.print(f"[green]✓[/green] Spotify connected (320kbps via {device.get('name', 'Connect')})")
                    else:
                        console.print("[green]✓[/green] Spotify connected (via YouTube)")
            else:
                console.print("[red]✗[/red] Spotify not configured")

        if "pandora" in enabled:
            sys.stdout.write("\033[33m→\033[0m Starting Tor for Pandora...")
            sys.stdout.flush()
            src = PandoraSource(self.config.get("pandora", {}))
            sys.stdout.write("\r\033[2K")  # Clear the line
            sys.stdout.flush()
            if src.is_configured():
                self.sources.append(src)
                console.print("[green]✓[/green] Pandora connected (via Tor)")
            else:
                error = src.error_message or "unknown error"
                console.print(f"[red]✗[/red] Pandora: {error}")

        if "youtube" in enabled:
            src = YouTubeSource(self.config.get("youtube", {}))
            if src.is_configured():
                self.sources.append(src)
                console.print("[green]✓[/green] YouTube Music available")

    def _init_scrobbler(self):
        """Initialize Last.fm scrobbler."""
        lastfm_config = self.config.get("lastfm", {})
        api_key = lastfm_config.get("api_key")
        api_secret = lastfm_config.get("api_secret")
        username = lastfm_config.get("username")
        password = lastfm_config.get("password")

        if not all([api_key, api_secret, username, password]):
            return

        if not PYLAST_AVAILABLE:
            console.print("[yellow]![/yellow] pylast not installed, scrobbling disabled")
            return

        password_hash = pylast.md5(password)
        self.scrobbler = Scrobbler(api_key, api_secret, username, password_hash)

        if self.scrobbler.enabled:
            console.print("[green]✓[/green] Last.fm scrobbling enabled")
        else:
            error = getattr(self.scrobbler, '_last_error', 'unknown error')
            console.print(f"[red]✗[/red] Last.fm: {error}")

    def _setup_callbacks(self):
        """Set up player callbacks."""
        self.player.on_track_end(self._on_track_end)

    def _on_track_end(self):
        """Called when current track ends."""
        self.play_next()

    def _loading_status(self, msg: str):
        """Show loading status on single line."""
        sys.stdout.write(f"\r\033[2K\033[33m→\033[0m {msg}")
        sys.stdout.flush()

    def load_queue(self, mode: str = "shuffle", seed: Optional[str] = None):
        """Load tracks into queue from all sources.

        Fast loading: Gets tracks directly from Spotify likes and Pandora radio.
        No slow YouTube searches. Press 'l' to manually add Last.fm recommendations.
        """
        self.queue = []
        source_counts = {}

        # Load from Spotify and Pandora (fast, direct API calls)
        for source in self.sources:
            try:
                self._loading_status(f"Loading {source.name.capitalize()} tracks...")

                if source.name == "spotify":
                    # Get liked songs directly (fast)
                    tracks = source.get_liked_tracks(limit=50)
                    if not tracks:
                        # Fallback to playlists
                        playlists = source.get_playlists()
                        if playlists:
                            playlist = random.choice(playlists)
                            tracks = source.get_tracks_from_playlist(playlist["id"])
                elif source.name == "pandora":
                    # Get radio tracks from QuickMix
                    tracks = source.get_radio_tracks(seed)
                elif source.name == "youtube":
                    # Use a seed from Spotify to get relevant recommendations
                    spotify_src = self._get_source("spotify")
                    if spotify_src:
                        liked = spotify_src.get_liked_tracks(limit=10)
                        if liked:
                            seed_track = random.choice(liked)
                            seed = f"{seed_track.artist} {seed_track.title}"
                            tracks = source.get_radio_tracks(seed)
                    if not tracks:
                        continue
                else:
                    tracks = source.get_radio_tracks(seed)

                # Filter out banned tracks
                tracks = [t for t in tracks if not is_banned(t.artist, t.title)]
                self.queue.extend(tracks)
                source_counts[source.name] = len(tracks)
            except Exception as e:
                console.print(f"\n[red]Error loading from {source.name}: {e}[/red]")

        # Clear loading message
        sys.stdout.write("\r\033[2K")
        sys.stdout.flush()

        if self.queue:
            random.shuffle(self.queue)
            breakdown = ", ".join(f"{name}: {count}" for name, count in source_counts.items())
            console.print(f"[green]Loaded {len(self.queue)} tracks ({breakdown})[/green]")
        else:
            console.print("[red]No tracks loaded! Check your configuration.[/red]")

    def play_next(self):
        """Play next track in queue."""
        if self._playing_next:
            return
        self._playing_next = True

        try:
            if self.current_track:
                self.history.append(self.current_track)

            if not self.queue:
                self.load_queue()

            self._refill_pandora_if_needed()

            if not self.queue:
                console.print("[red]Queue empty, nothing to play[/red]")
                return

            track = self.queue.pop(0)

            source = self._get_source(track.source)
            if source:
                track.url = source.get_stream_url(track)

            self.player.play(track)
            self.current_track = track
            self.current_genres = []
            self.current_loved = False
            self.current_scrobbled = False
            self._current_position = 0.0
            # Clear old status and reset for fresh print
            if not self._status_first_print:
                sys.stdout.write("\033[2K\033[A\033[2K\r")
                sys.stdout.flush()
            self._status_first_print = True

            if self.scrobbler and self.scrobbler.enabled:
                self.scrobbler.now_playing(track)
                def fetch_track_info():
                    self.current_genres = self.scrobbler.get_track_tags(track)
                    self.current_loved = self.scrobbler.is_loved(track)
                threading.Thread(target=fetch_track_info, daemon=True).start()

            # Clear display for fresh status
            sys.stdout.write("\r\033[K\n\033[K\033[A")
            sys.stdout.flush()
        finally:
            self._playing_next = False

    def _refill_pandora_if_needed(self):
        """Fetch more Pandora tracks when queue is running low."""
        pandora_in_queue = sum(1 for t in self.queue if t.source == "pandora")
        if pandora_in_queue < 3:
            pandora_src = self._get_source("pandora")
            if pandora_src:
                # Fetch in background to not block
                def fetch():
                    try:
                        new_tracks = pandora_src.get_radio_tracks()
                        if new_tracks:
                            # Insert randomly into queue
                            for track in new_tracks:
                                pos = random.randint(0, max(1, len(self.queue)))
                                self.queue.insert(pos, track)
                    except Exception:
                        pass
                threading.Thread(target=fetch, daemon=True).start()

    def _get_source(self, name: str) -> Optional[MusicSource]:
        """Get source by name."""
        for src in self.sources:
            if src.name == name:
                return src
        return None

    def love_current(self):
        """Love/like current track."""
        if not self.current_track:
            return

        self._clear_status()

        loved_on = []

        # Love on source service
        source = self._get_source(self.current_track.source)
        if source and source.love_track(self.current_track):
            loved_on.append(self.current_track.source.capitalize())

        # Love on Last.fm
        if self.scrobbler and self.scrobbler.love_track(self.current_track):
            loved_on.append("Last.fm")

        if loved_on:
            services = ", ".join(loved_on)
            console.print(f"[red]♥[/red] [green]Loved on {services}[/green]")
            console.print()
        else:
            console.print("[yellow]Love failed[/yellow]")
            console.print()

    def ban_current(self):
        """Ban/dislike current track."""
        if not self.current_track:
            return

        self._clear_status()

        # Always save to local ban list
        add_banned(self.current_track.artist, self.current_track.title)

        # Also try to ban on source (e.g., Pandora thumbs down)
        source = self._get_source(self.current_track.source)
        if source:
            source.ban_track(self.current_track)

        console.print(f"[red]✗ Banned:[/red] {self.current_track.artist} - {self.current_track.title}")
        console.print()
        self.play_next()

    def toggle_pause(self):
        """Toggle pause state."""
        self.player.pause()
        self.paused = self.player.paused

    def show_info(self):
        """Show detailed track info."""
        self._clear_status()
        if not self.current_track:
            console.print("[yellow]No track playing[/yellow]")
            console.print()
            return

        track = self.current_track
        table = Table(title="Track Info", box=box.ROUNDED)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Title", track.title)
        table.add_row("Artist", track.artist)
        table.add_row("Album", track.album or "-")
        table.add_row("Source", track.source.capitalize())
        table.add_row("Duration", f"{track.duration // 60}:{track.duration % 60:02d}")
        table.add_row("Queue", f"{len(self.queue)} tracks remaining")
        if self.current_genres:
            table.add_row("Genres", ", ".join(self.current_genres))
        # Audio quality
        if self.player.audio_bitrate:
            table.add_row("Quality", f"{self.player.audio_bitrate}kbps {self.player.audio_codec}")

        console.print(table)
        console.print()

    def show_help(self):
        """Show help."""
        self._clear_status()
        console.print(Panel(HELP_TEXT, title="Help", border_style="magenta"))
        console.print()

    def _print_status(self):
        """Print the current status line."""
        # Move to beginning of line, clear it, print status
        sys.stdout.write("\033[2K\r")  # Clear line
        console.print(self._get_status_line(), end="")
        sys.stdout.flush()

    def run(self):
        """Main run loop."""
        console.print(Panel.fit(
            "[bold magenta]OmniShuffle[/bold magenta]\n"
            "Unified music shuffler for Spotify, Pandora & YouTube",
            border_style="magenta"
        ))
        console.print()

        if not self.sources:
            console.print("[red]No sources configured![/red]")
            console.print(f"Edit config at: {get_config_dir() / 'config.json'}")
            return

        # Load initial queue
        mode = self.config.get("general", {}).get("default_mode", "shuffle")
        self.load_queue(mode)

        if not self.queue:
            return

        self.running = True
        self.play_next()

        console.print("[dim]Press 'h' for help, 'q' to quit[/dim]")
        print()  # Empty line for status display

        # Start status updater thread
        self.status_thread = threading.Thread(target=self._status_updater, daemon=True)
        self.status_thread.start()

        try:
            while self.running:
                try:
                    key = readchar.readchar()
                except KeyboardInterrupt:
                    break

                if key == 'q':
                    self.running = False
                elif key == 'n':
                    self.play_next()
                elif key == 'p' or key == ' ':
                    self.toggle_pause()
                elif key == '+' or key == '=':
                    self.love_current()
                elif key == '-':
                    self.ban_current()
                elif key == '(':
                    self.player.volume_down()
                elif key == ')':
                    self.player.volume_up()
                elif key == 'i':
                    self.show_info()
                elif key == 'h' or key == '?':
                    self.show_help()
                elif key == 'S':
                    self._clear_status()
                    random.shuffle(self.queue)
                    console.print("[green]Queue shuffled![/green]")
                    console.print()
                elif key == 'l':
                    self._clear_status()
                    if self.scrobbler and self.scrobbler.enabled:
                        console.print("[dim]Loading Last.fm recommendations...[/dim]")
                        console.print()
                        self.load_queue("lastfm")
                        if self.queue:
                            self.play_next()
                    else:
                        console.print("[yellow]Last.fm not configured[/yellow]")
                        console.print()

        finally:
            self.running = False
            self.player.shutdown()
            self._clear_status()
            console.print("[magenta]Goodbye![/magenta]")


def main():
    """Entry point."""
    app = OmniShuffle()
    app.run()


if __name__ == "__main__":
    main()
