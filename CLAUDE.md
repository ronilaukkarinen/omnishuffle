# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project overview

OmniShuffle is a command-line music shuffler that unifies Spotify, Pandora, and YouTube Music into a single streaming experience with pianobar-style controls and Last.fm scrobbling support.

## Architecture

- `omnishuffle/` - Main Python package
- `omnishuffle/sources/` - Music source integrations (Spotify, Pandora, YouTube)
- `omnishuffle/player.py` - MPV-based playback with MPRIS support
- `omnishuffle/main.py` - CLI interface with keyboard controls
- `omnishuffle/config.py` - Configuration management

### Directory structure

```
omnishuffle/
├── __init__.py
├── config.py              # Configuration loading/saving
├── main.py                # CLI entry point and keyboard controls
├── player.py              # MPV player wrapper with MPRIS
└── sources/
    ├── __init__.py
    ├── base.py            # Abstract base class for sources
    ├── spotify.py         # Spotify integration via spotipy
    ├── pandora.py         # Pandora integration via pydora
    └── youtube.py         # YouTube Music via ytmusicapi
```

## Common commands

```bash
pipx install -e .          # Install in development mode
omnishuffle                # Run the player
```

## Configuration

Config file: `~/.config/omnishuffle/config.json`

## Key guidelines

- Uses MPV for playback (supports MPRIS for Last.fm scrobbling via rescrobbled)
- Spotify tracks are played via YouTube search (no Spotify Premium required)
- Pandora requires Tor proxy for non-US users
- YouTube works without authentication

## Commits and code style

- One logical change per commit
- Keep commit messages concise (one line), use sentence case
- Update CHANGELOG.md for user-facing changes
- Use present tense in commits and CHANGELOG.md
- Use sentence case for headings (not Title Case)
- Never use bold text as headings, use proper heading levels instead
- Always add an empty line after headings
- No formatting in CHANGELOG.md except `inline code` and when absolute necessary
- Use * as bullets in CHANGELOG.md
- No Claude watermark in commits
- No emojis in commits or code
- Keep CHANGELOG.md date up to date when adding entries
