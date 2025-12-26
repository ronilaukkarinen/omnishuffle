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

from omnishuffle.config import load_config, get_config_dir
from omnishuffle.player import Player, Track
from omnishuffle.sources import SpotifySource, PandoraSource, YouTubeSource, MusicSource


console = Console()

# EQ-style animation frames (two vertical bars with space)
SPINNER_FRAMES = ["▁ ▃", "▃ ▅", "▅ ▇", "▇ ▅", "▅ ▃", "▃ ▁", "▂ ▆", "▆ ▂"]


HELP_TEXT = """
[bold magenta]OmniShuffle Controls[/bold magenta]

[magenta]n[/magenta]  Next track          [magenta]p[/magenta]  Pause/Resume
[magenta]+[/magenta]  Love track          [magenta]-[/magenta]  Ban track (Pandora)
[magenta]([/magenta]  Volume down         [magenta])[/magenta]  Volume up
[magenta]s[/magenta]  Switch station      [magenta]S[/magenta]  Shuffle sources
[magenta]i[/magenta]  Track info          [magenta]h[/magenta]  Show help
[magenta]q[/magenta]  Quit
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

        self._init_sources()
        self._setup_callbacks()

    def _get_status_line(self) -> str:
        """Generate the status line with spinner as plain string with ANSI colors."""
        if not self.current_track:
            return "\033[2m  No track playing\033[0m"

        track = self.current_track

        # ANSI color codes for brand colors
        colors = {
            "spotify": "\033[38;2;29;185;84m",   # #1DB954
            "pandora": "\033[38;2;54;104;255m",  # #3668FF
            "youtube": "\033[38;2;255;0;0m",     # #FF0000
        }
        reset = "\033[0m"
        bold = "\033[1m"
        dim = "\033[2m"
        dimmer = "\033[38;2;100;100;100m"  # Dark grey for volume
        white = "\033[97m"

        color = colors.get(track.source, white)

        # Get spinner frame
        if self.paused:
            spinner = "⏸"
        else:
            spinner = SPINNER_FRAMES[self.spinner_idx % len(SPINNER_FRAMES)]

        # Build status line
        return (
            f" {bold}{color}{spinner}{reset} "
            f"{color}[{track.source.upper()}]{reset} "
            f"{bold}{white}{track.title}{reset}"
            f"{dim} - {reset}"
            f"{track.artist}"
            f"{dimmer}  vol {self.player.volume}%{reset}"
        )

    def _status_updater(self):
        """Background thread to update spinner."""
        while self.running:
            with self.status_lock:
                self.spinner_idx += 1
            # Clear line and print status
            status = self._get_status_line()
            sys.stdout.write(f"\033[2K\r{status}")
            sys.stdout.flush()
            time.sleep(0.1)

    def _init_sources(self):
        """Initialize enabled music sources."""
        enabled = self.config.get("general", {}).get("sources", [])

        if "spotify" in enabled:
            src = SpotifySource(self.config.get("spotify", {}))
            if src.is_configured():
                self.sources.append(src)
                console.print("[green]✓[/green] Spotify connected")
            else:
                console.print("[red]✗[/red] Spotify not configured")

        if "pandora" in enabled:
            sys.stdout.write("  Starting Tor for Pandora...")
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

    def _setup_callbacks(self):
        """Set up player callbacks."""
        self.player.on_track_end(self._on_track_end)

    def _on_track_end(self):
        """Called when current track ends."""
        self.play_next()

    def load_queue(self, mode: str = "shuffle", seed: Optional[str] = None):
        """Load tracks into queue from all sources."""
        self.queue = []

        for source in self.sources:
            try:
                if mode == "radio":
                    tracks = source.get_radio_tracks(seed)
                else:
                    # Get from playlists
                    playlists = source.get_playlists()
                    if playlists:
                        # Pick random playlist
                        playlist = random.choice(playlists)
                        tracks = source.get_tracks_from_playlist(playlist["id"])
                    else:
                        tracks = source.get_radio_tracks()

                self.queue.extend(tracks)
            except Exception as e:
                console.print(f"[red]Error loading from {source.name}: {e}[/red]")

        if self.queue:
            random.shuffle(self.queue)
            console.print(f"[green]Loaded {len(self.queue)} tracks from {len(self.sources)} sources[/green]")
        else:
            console.print("[red]No tracks loaded! Check your configuration.[/red]")

    def play_next(self):
        """Play next track in queue."""
        if self.current_track:
            self.history.append(self.current_track)

        if not self.queue:
            # Refill queue
            self.load_queue()

        if not self.queue:
            console.print("[red]Queue empty, nothing to play[/red]")
            return

        track = self.queue.pop(0)
        self.current_track = track

        # Get stream URL
        source = self._get_source(track.source)
        if source:
            track.url = source.get_stream_url(track)

        self.player.play(track)
        self._show_now_playing()

    def _get_source(self, name: str) -> Optional[MusicSource]:
        """Get source by name."""
        for src in self.sources:
            if src.name == name:
                return src
        return None

    def _show_now_playing(self):
        """Display current track info."""
        if not self.current_track:
            return

        track = self.current_track
        source_colors = {
            "spotify": "green",
            "pandora": "blue",
            "youtube": "red",
        }
        color = source_colors.get(track.source, "white")

        console.print()
        console.print(f"[{color}]▶ {track.source.upper()}[/{color}]")
        console.print(f"[bold white]{track.title}[/bold white]")
        console.print(f"[cyan]{track.artist}[/cyan]")
        if track.album:
            console.print(f"[dim]{track.album}[/dim]")
        console.print()

    def love_current(self):
        """Love/like current track."""
        if not self.current_track:
            return

        source = self._get_source(self.current_track.source)
        if source and source.love_track(self.current_track):
            console.print("[green]♥ Loved![/green]")
        else:
            console.print("[yellow]Love not supported for this source[/yellow]")

    def ban_current(self):
        """Ban/dislike current track."""
        if not self.current_track:
            return

        source = self._get_source(self.current_track.source)
        if source and source.ban_track(self.current_track):
            console.print("[red]✗ Banned![/red]")
            self.play_next()
        else:
            console.print("[yellow]Ban not supported for this source[/yellow]")

    def toggle_pause(self):
        """Toggle pause state."""
        self.player.pause()
        self.paused = self.player.paused
        if self.paused:
            console.print("[yellow]⏸ Paused[/yellow]")
        else:
            console.print("[green]▶ Playing[/green]")

    def show_info(self):
        """Show detailed track info."""
        if not self.current_track:
            console.print("[yellow]No track playing[/yellow]")
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

        console.print(table)

    def show_help(self):
        """Show help."""
        console.print(Panel(HELP_TEXT, title="Help", border_style="magenta"))

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
        console.print()

        # Start status updater thread
        self.status_thread = threading.Thread(target=self._status_updater, daemon=True)
        self.status_thread.start()

        try:
            while self.running:
                try:
                    key = readchar.readchar()
                except KeyboardInterrupt:
                    break

                # Clear status line before printing anything
                sys.stdout.write("\033[2K\r")

                if key == 'q':
                    self.running = False
                elif key == 'n':
                    console.print("[dim]Skipping...[/dim]")
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
                    console.print()  # New line before info
                    self.show_info()
                elif key == 'h' or key == '?':
                    console.print()  # New line before help
                    self.show_help()
                elif key == 'S':
                    random.shuffle(self.queue)
                    console.print("[green]Queue shuffled![/green]")

        finally:
            self.running = False
            self.player.shutdown()
            sys.stdout.write("\033[2K\r")  # Clear status line
            console.print("[magenta]Goodbye![/magenta]")


def main():
    """Entry point."""
    app = OmniShuffle()
    app.run()


if __name__ == "__main__":
    main()
