"""MPRIS2 D-Bus interface for OmniShuffle (Linux only)."""

import asyncio
import hashlib
import platform
import threading
import time
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
  from omnishuffle.player import Player, Track

# Only available on Linux with dbus-next installed
MPRIS_AVAILABLE = False
if platform.system() == "Linux":
  try:
    from dbus_next.aio import MessageBus
    from dbus_next.service import ServiceInterface, dbus_property, method
    from dbus_next import Variant
    MPRIS_AVAILABLE = True
  except ImportError:
    pass


if MPRIS_AVAILABLE:
  class MediaPlayer2Interface(ServiceInterface):
    """org.mpris.MediaPlayer2 interface."""

    def __init__(self, quit_callback: Callable):
      super().__init__("org.mpris.MediaPlayer2")
      self._quit_callback = quit_callback

    @dbus_property()
    def CanQuit(self) -> "b":
      return True

    @dbus_property()
    def CanRaise(self) -> "b":
      return False

    @dbus_property()
    def HasTrackList(self) -> "b":
      return False

    @dbus_property()
    def Identity(self) -> "s":
      return "OmniShuffle"

    @dbus_property()
    def SupportedUriSchemes(self) -> "as":
      return []

    @dbus_property()
    def SupportedMimeTypes(self) -> "as":
      return []

    @method()
    def Raise(self):
      pass

    @method()
    def Quit(self):
      if self._quit_callback:
        self._quit_callback()


  class PlayerInterface(ServiceInterface):
    """org.mpris.MediaPlayer2.Player interface."""

    def __init__(self, player: "Player", next_callback: Callable,
                 pause_callback: Callable, stop_callback: Callable):
      super().__init__("org.mpris.MediaPlayer2.Player")
      self._player = player
      self._next_callback = next_callback
      self._pause_callback = pause_callback
      self._stop_callback = stop_callback

    def _get_track_id(self) -> str:
      """Generate D-Bus object path for current track."""
      if self._player.current_track and self._player.current_track.track_id:
        h = hashlib.md5(self._player.current_track.track_id.encode()).hexdigest()[:16]
        return f"/org/mpris/MediaPlayer2/Track/{h}"
      return "/org/mpris/MediaPlayer2/TrackList/NoTrack"

    @dbus_property()
    def PlaybackStatus(self) -> "s":
      if not self._player.current_track:
        return "Stopped"
      return "Paused" if self._player.paused else "Playing"

    @dbus_property()
    def LoopStatus(self) -> "s":
      return "None"

    @LoopStatus.setter
    def LoopStatus_setter(self, value: "s"):
      pass

    @dbus_property()
    def Rate(self) -> "d":
      return 1.0

    @Rate.setter
    def Rate_setter(self, value: "d"):
      pass

    @dbus_property()
    def Shuffle(self) -> "b":
      return True

    @Shuffle.setter
    def Shuffle_setter(self, value: "b"):
      pass

    @dbus_property()
    def Metadata(self) -> "a{sv}":
      track = self._player.current_track
      if not track:
        return {"mpris:trackid": Variant("o", "/org/mpris/MediaPlayer2/TrackList/NoTrack")}

      metadata = {
        "mpris:trackid": Variant("o", self._get_track_id()),
        "mpris:length": Variant("x", int(track.duration * 1_000_000)),
        "xesam:title": Variant("s", track.title or ""),
        "xesam:artist": Variant("as", [track.artist] if track.artist else []),
        "xesam:album": Variant("s", track.album or ""),
      }

      if track.artwork_url:
        metadata["mpris:artUrl"] = Variant("s", track.artwork_url)

      return metadata

    @dbus_property()
    def Volume(self) -> "d":
      return self._player.volume / 100.0

    @Volume.setter
    def Volume_setter(self, value: "d"):
      self._player.set_volume(int(value * 100))

    @dbus_property()
    def Position(self) -> "x":
      return int(self._player.position * 1_000_000)

    @dbus_property()
    def MinimumRate(self) -> "d":
      return 1.0

    @dbus_property()
    def MaximumRate(self) -> "d":
      return 1.0

    @dbus_property()
    def CanGoNext(self) -> "b":
      return True

    @dbus_property()
    def CanGoPrevious(self) -> "b":
      return False

    @dbus_property()
    def CanPlay(self) -> "b":
      return True

    @dbus_property()
    def CanPause(self) -> "b":
      return True

    @dbus_property()
    def CanSeek(self) -> "b":
      return False

    @dbus_property()
    def CanControl(self) -> "b":
      return True

    @method()
    def Next(self):
      if self._next_callback:
        self._next_callback()

    @method()
    def Previous(self):
      pass

    @method()
    def Pause(self):
      if not self._player.paused and self._pause_callback:
        self._pause_callback()

    @method()
    def PlayPause(self):
      if self._pause_callback:
        self._pause_callback()

    @method()
    def Stop(self):
      if self._stop_callback:
        self._stop_callback()

    @method()
    def Play(self):
      if self._player.paused and self._pause_callback:
        self._pause_callback()

    @method()
    def Seek(self, offset: "x"):
      pass

    @method()
    def SetPosition(self, track_id: "o", position: "x"):
      pass

    @method()
    def OpenUri(self, uri: "s"):
      pass


class MPRISService:
  """MPRIS2 D-Bus service manager."""

  def __init__(self, player: "Player", next_callback: Callable,
               pause_callback: Callable, stop_callback: Callable,
               quit_callback: Callable):
    self._player = player
    self._next_callback = next_callback
    self._pause_callback = pause_callback
    self._stop_callback = stop_callback
    self._quit_callback = quit_callback

    self._loop: Optional[asyncio.AbstractEventLoop] = None
    self._thread: Optional[threading.Thread] = None
    self._bus = None
    self._mp2_interface = None
    self._player_interface = None
    self._running = False
    self._ready = threading.Event()

  def start(self):
    """Start MPRIS service in background thread."""
    if not MPRIS_AVAILABLE:
      return False

    self._running = True
    self._thread = threading.Thread(target=self._run_loop, daemon=True)
    self._thread.start()

    # Wait for D-Bus to be ready (up to 2 seconds)
    self._ready.wait(timeout=2.0)
    return self._ready.is_set()

  def _run_loop(self):
    """Run asyncio event loop in dedicated thread."""
    self._loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self._loop)

    try:
      self._loop.run_until_complete(self._setup_dbus())
      self._ready.set()
      self._loop.run_forever()
    except Exception as e:
      import sys
      print(f"MPRIS error: {e}", file=sys.stderr)
    finally:
      self._loop.close()

  async def _setup_dbus(self):
    """Set up D-Bus connection and export interfaces."""
    self._bus = await MessageBus().connect()

    self._mp2_interface = MediaPlayer2Interface(self._quit_callback)
    self._player_interface = PlayerInterface(
      self._player, self._next_callback, self._pause_callback, self._stop_callback
    )

    self._bus.export("/org/mpris/MediaPlayer2", self._mp2_interface)
    self._bus.export("/org/mpris/MediaPlayer2", self._player_interface)

    await self._bus.request_name("org.mpris.MediaPlayer2.omnishuffle")

  def notify_track_changed(self):
    """Notify MPRIS clients that track metadata changed."""
    if self._loop and self._player_interface and self._running:
      self._loop.call_soon_threadsafe(self._do_notify_track_changed)

  def _do_notify_track_changed(self):
    """Actually emit the track changed signal (runs in MPRIS thread)."""
    if self._player_interface:
      try:
        changed = {
          "Metadata": Variant("a{sv}", self._player_interface.Metadata),
          "PlaybackStatus": Variant("s", self._player_interface.PlaybackStatus),
        }
        self._player_interface.emit_properties_changed(changed)
      except Exception:
        pass

  def notify_playback_status_changed(self):
    """Notify MPRIS clients that playback status changed."""
    if self._loop and self._player_interface and self._running:
      self._loop.call_soon_threadsafe(self._do_notify_playback_status_changed)

  def _do_notify_playback_status_changed(self):
    """Actually emit the playback status signal (runs in MPRIS thread)."""
    if self._player_interface:
      try:
        changed = {
          "PlaybackStatus": Variant("s", self._player_interface.PlaybackStatus),
        }
        self._player_interface.emit_properties_changed(changed)
      except Exception:
        pass

  def notify_volume_changed(self):
    """Notify MPRIS clients that volume changed."""
    if self._loop and self._player_interface and self._running:
      self._loop.call_soon_threadsafe(self._do_notify_volume_changed)

  def _do_notify_volume_changed(self):
    """Actually emit the volume changed signal (runs in MPRIS thread)."""
    if self._player_interface:
      try:
        changed = {
          "Volume": Variant("d", self._player_interface.Volume),
        }
        self._player_interface.emit_properties_changed(changed)
      except Exception:
        pass

  def stop(self):
    """Stop MPRIS service."""
    self._running = False
    if self._loop:
      self._loop.call_soon_threadsafe(self._loop.stop)
