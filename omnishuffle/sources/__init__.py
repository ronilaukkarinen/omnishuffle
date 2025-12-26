"""Music source providers."""

from omnishuffle.sources.base import MusicSource
from omnishuffle.sources.spotify import SpotifySource
from omnishuffle.sources.pandora import PandoraSource
from omnishuffle.sources.youtube import YouTubeSource

__all__ = ["MusicSource", "SpotifySource", "PandoraSource", "YouTubeSource"]
