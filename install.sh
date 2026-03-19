#!/bin/bash
# OmniShuffle installer - works on macOS and Linux
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

print_header() {
  echo -e "\n${MAGENTA}${BOLD}$1${NC}\n"
}

print_step() {
  echo -e "${CYAN}→${NC} $1"
}

print_success() {
  echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
  echo -e "${YELLOW}!${NC} $1"
}

print_error() {
  echo -e "${RED}✗${NC} $1"
}

# Detect OS
detect_os() {
  if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    if ! command -v brew &> /dev/null; then
      print_error "Homebrew is required on macOS. Install it from https://brew.sh"
      exit 1
    fi
  elif [[ -f /etc/arch-release ]]; then
    OS="arch"
  elif [[ -f /etc/debian_version ]]; then
    OS="debian"
  elif [[ -f /etc/fedora-release ]]; then
    OS="fedora"
  else
    OS="unknown"
  fi
  echo "$OS"
}

# Install dependencies based on OS
install_deps() {
  local os=$1
  print_header "Installing dependencies"

  case $os in
    macos)
      print_step "Installing via Homebrew..."
      brew install mpv ffmpeg tor pipx 2>/dev/null || brew upgrade mpv ffmpeg tor pipx 2>/dev/null || true
      # Rebuild mpv against current ffmpeg to prevent symbol mismatch (e.g. _av_base64_encode)
      if ! python3 -c "import ctypes; ctypes.CDLL('libmpv.dylib')" 2>/dev/null; then
        print_step "Rebuilding mpv to match current ffmpeg..."
        brew reinstall mpv 2>/dev/null || true
      fi
      pipx ensurepath 2>/dev/null || true
      ;;
    arch)
      print_step "Installing via pacman..."
      sudo pacman -S --noconfirm --needed mpv ffmpeg tor python-pipx
      ;;
    debian)
      print_step "Installing via apt..."
      sudo apt update
      sudo apt install -y mpv ffmpeg tor pipx
      pipx ensurepath 2>/dev/null || true
      ;;
    fedora)
      print_step "Installing via dnf..."
      sudo dnf install -y mpv ffmpeg tor pipx
      pipx ensurepath 2>/dev/null || true
      ;;
    *)
      print_warning "Unknown OS. Please install manually: mpv, ffmpeg, tor, pipx"
      ;;
  esac

  print_success "Dependencies installed"
}

# Prompt for optional input with default
prompt_optional() {
  local prompt=$1
  local default=$2
  local var_name=$3
  local is_password=$4

  if [[ "$is_password" == "true" ]]; then
    echo -ne "${CYAN}?${NC} $prompt: "
    read -s value
    echo
  else
    echo -ne "${CYAN}?${NC} $prompt${default:+ [$default]}: "
    read value
  fi

  if [[ -z "$value" ]]; then
    eval "$var_name='$default'"
  else
    eval "$var_name='$value'"
  fi
}

# Prompt yes/no
prompt_yn() {
  local prompt=$1
  local default=$2
  echo -ne "${CYAN}?${NC} $prompt [y/n] ($default): "
  read answer
  answer=${answer:-$default}
  [[ "$answer" =~ ^[Yy] ]]
}

# Install and configure spotifyd for 320kbps Spotify streaming
setup_spotifyd() {
  local os=$1

  print_header "Spotify Connect setup (320kbps streaming)"

  if ! prompt_yn "Set up spotifyd for 320kbps Spotify streaming? (requires Premium)" "y"; then
    print_step "Skipping spotifyd setup (will use YouTube fallback)"
    return
  fi

  # Install spotifyd
  print_step "Installing spotifyd..."
  case $os in
    macos)
      brew install spotifyd 2>/dev/null || brew upgrade spotifyd 2>/dev/null || true
      ;;
    arch)
      if command -v yay &> /dev/null; then
        yay -S --noconfirm spotifyd
      elif command -v paru &> /dev/null; then
        paru -S --noconfirm spotifyd
      else
        print_warning "Install spotifyd from AUR: yay -S spotifyd"
        return
      fi
      ;;
    debian|fedora)
      print_warning "spotifyd not in repos. Install from: https://github.com/Spotifyd/spotifyd/releases"
      return
      ;;
  esac

  # Create config directory
  mkdir -p "$HOME/.config/spotifyd"
  mkdir -p "$HOME/.config/spotifyd/cache"

  # Check for existing credentials
  if [[ -f "$HOME/.config/spotifyd/credentials.json" ]]; then
    print_success "Found existing Spotify credentials"
  else
    echo ""
    echo "You need Spotify credentials for spotifyd."
    echo "Find your username at: https://www.spotify.com/account"
    echo ""
    prompt_optional "Spotify username" "" "spotify_username"
    prompt_optional "Spotify password" "" "spotify_password" "true"

    if [[ -n "$spotify_username" && -n "$spotify_password" ]]; then
      # Create config with credentials
      local backend="pulseaudio"
      local device_name="OmniShuffle"
      if [[ "$os" == "macos" ]]; then
        backend="portaudio"
        device_name="OmniShuffle-Mac"
      fi

      cat > "$HOME/.config/spotifyd/spotifyd.conf" << EOF
[global]
username = "$spotify_username"
password = "$spotify_password"
backend = "$backend"
device_name = "$device_name"
bitrate = 320
volume_normalisation = true
normalisation_pregain = -10
cache_path = "$HOME/.config/spotifyd/cache"
EOF
      print_success "Created spotifyd config with credentials"
    fi
  fi

  # Create config without credentials if we have credentials.json
  if [[ -f "$HOME/.config/spotifyd/credentials.json" && ! -f "$HOME/.config/spotifyd/spotifyd.conf" ]]; then
    local backend="pulseaudio"
    local device_name="OmniShuffle"
    if [[ "$os" == "macos" ]]; then
      backend="portaudio"
      device_name="OmniShuffle-Mac"
    fi

    cat > "$HOME/.config/spotifyd/spotifyd.conf" << EOF
[global]
backend = "$backend"
device_name = "$device_name"
bitrate = 320
volume_normalisation = true
normalisation_pregain = -10
cache_path = "$HOME/.config/spotifyd/cache"
EOF
    print_success "Created spotifyd config"
  fi

  # Start spotifyd service
  print_step "Starting spotifyd..."
  case $os in
    macos)
      brew services start spotifyd 2>/dev/null || true
      print_success "spotifyd started (will auto-start on boot)"
      ;;
    arch|debian|fedora)
      systemctl --user enable --now spotifyd 2>/dev/null || true
      print_success "spotifyd started (will auto-start on login)"
      ;;
  esac
}

# Create config file
create_config() {
  print_header "OmniShuffle configuration"

  local config_dir="$HOME/.config/omnishuffle"
  local config_file="$config_dir/config.json"

  mkdir -p "$config_dir"

  # Check for existing config
  if [[ -f "$config_file" ]]; then
    print_warning "Config file already exists at $config_file"
    if ! prompt_yn "Overwrite existing config?" "n"; then
      print_step "Keeping existing config"
      return
    fi
  fi

  # Sources to enable
  local sources=()
  echo -e "\n${BOLD}Which music sources do you want to enable?${NC}"

  if prompt_yn "Enable Spotify?" "y"; then
    sources+=("spotify")
  fi
  if prompt_yn "Enable Pandora?" "y"; then
    sources+=("pandora")
  fi
  if prompt_yn "Enable YouTube Music?" "y"; then
    sources+=("youtube")
  fi

  # Spotify config
  local spotify_client_id=""
  local spotify_client_secret=""
  if [[ " ${sources[*]} " =~ " spotify " ]]; then
    print_header "Spotify API setup"
    echo "Get credentials from: https://developer.spotify.com/dashboard"
    echo "1. Create an app"
    echo "2. Set redirect URI to: http://127.0.0.1:8080"
    echo ""
    prompt_optional "Spotify Client ID" "" "spotify_client_id"
    prompt_optional "Spotify Client Secret" "" "spotify_client_secret"
  fi

  # Pandora config
  local pandora_email=""
  local pandora_password=""
  local pandora_proxy=""
  if [[ " ${sources[*]} " =~ " pandora " ]]; then
    print_header "Pandora setup"
    prompt_optional "Pandora email" "" "pandora_email"
    prompt_optional "Pandora password" "" "pandora_password" "true"
    if prompt_yn "Are you outside the USA? (enables Tor proxy)" "n"; then
      pandora_proxy="socks5://127.0.0.1:9050"
    fi
  fi

  # Last.fm config
  local lastfm_api_key=""
  local lastfm_api_secret=""
  local lastfm_username=""
  local lastfm_password=""
  if prompt_yn "Enable Last.fm scrobbling?" "y"; then
    print_header "Last.fm setup"
    echo "Get API credentials from: https://www.last.fm/api/account/create"
    echo ""
    prompt_optional "Last.fm API Key" "" "lastfm_api_key"
    prompt_optional "Last.fm API Secret" "" "lastfm_api_secret"
    prompt_optional "Last.fm Username" "" "lastfm_username"
    prompt_optional "Last.fm Password" "" "lastfm_password" "true"
  fi

  # Build sources JSON array
  local sources_json=""
  for src in "${sources[@]}"; do
    if [[ -n "$sources_json" ]]; then
      sources_json+=", "
    fi
    sources_json+="\"$src\""
  done

  # Write config file
  cat > "$config_file" << EOF
{
  "general": {
    "default_mode": "shuffle",
    "sources": [$sources_json],
    "volume": 100
  },
  "spotify": {
    "client_id": "$spotify_client_id",
    "client_secret": "$spotify_client_secret",
    "redirect_uri": "http://127.0.0.1:8080"
  },
  "pandora": {
    "email": "$pandora_email",
    "password": "$pandora_password",
    "proxy": "$pandora_proxy"
  },
  "lastfm": {
    "api_key": "$lastfm_api_key",
    "api_secret": "$lastfm_api_secret",
    "username": "$lastfm_username",
    "password": "$lastfm_password"
  }
}
EOF

  print_success "Config saved to $config_file"
}

# Install OmniShuffle
install_omnishuffle() {
  print_header "Installing OmniShuffle"

  # Get the directory where this script is located
  local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  if [[ -f "$script_dir/pyproject.toml" ]]; then
    print_step "Installing from local directory..."
    pipx install -e "$script_dir" --force
  else
    print_step "Installing from GitHub..."
    pipx install git+https://github.com/ronilaukkarinen/omnishuffle.git --force
  fi

  print_success "OmniShuffle installed"
}

# Main
main() {
  echo -e "${MAGENTA}${BOLD}"
  echo "  ___                  _ ____  _            __  __ _      "
  echo " / _ \ _ __ ___  _ __ (_) ___|| |__  _   _ / _|/ _| | ___ "
  echo "| | | | '_ \` _ \| '_ \| \___ \| '_ \| | | | |_| |_| |/ _ \\"
  echo "| |_| | | | | | | | | | |___) | | | | |_| |  _|  _| |  __/"
  echo " \___/|_| |_| |_|_| |_|_|____/|_| |_|\__,_|_| |_| |_|\___|"
  echo -e "${NC}"
  echo -e "Unified music shuffler for Spotify, Pandora & YouTube\n"

  local os=$(detect_os)
  print_step "Detected OS: $os"

  install_deps "$os"
  create_config
  setup_spotifyd "$os"
  install_omnishuffle

  print_header "Installation complete!"
  echo -e "Run ${BOLD}omnishuffle${NC} to start playing music."
  echo -e "Press ${BOLD}h${NC} for help, ${BOLD}q${NC} to quit.\n"

  if prompt_yn "Start OmniShuffle now?" "y"; then
    exec omnishuffle
  fi
}

main "$@"
