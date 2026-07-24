#!/usr/bin/env bash
#
# Complete PiCarXTalk setup for Raspberry Pi OS / Debian.
#
# This script is safe to run again. It performs these setup steps:
#   1. Installs OS build, audio, LCD, and Python prerequisites.
#   2. Installs SunFounder Robot HAT and Vilib when they are missing.
#   3. Finds or downloads the Waveshare LCD Python driver.
#   4. Creates example/.venv-whisper and installs all Python packages.
#   5. Downloads the Vosk wake-word, faster-whisper, and Piper voice models.
#   6. Enables the Robot HAT I2S speaker overlay when it is missing.
#   7. Checks Codex login, audio devices, Raspberry Pi buses, and imports.
#
# Optional environment switches:
#   SKIP_APT=1             Do not install missing Debian packages.
#   SKIP_HARDWARE_LIBS=1   Do not install missing Robot HAT / Vilib packages.
#   SKIP_MODELS=1          Do not pre-download speech models.
#   SKIP_CODEX_INSTALL=1   Do not install Codex CLI when it is missing.
#   CONFIGURE_I2S=0        Do not enable the Robot HAT I2S speaker overlay.
#   WHISPER_MODEL=base     Select the faster-whisper model to cache.
#   PIPER_TTS_MODEL=en_US-lessac-high

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLE_DIR="${PROJECT_ROOT}/example"
VENV_DIR="${EXAMPLE_DIR}/.venv-whisper"
SETUP_SOURCE_DIR="${PROJECT_ROOT}/.setup-src"
USER_BASE="${HOME:?HOME must be set}"
VOSK_MODEL_DIR="${USER_BASE}/.vosk_models/vosk-model-small-en-us-0.15"
WHISPER_MODEL="${WHISPER_MODEL:-base}"
PIPER_TTS_MODEL="${PIPER_TTS_MODEL:-en_US-lessac-high}"
REBOOT_REQUIRED=0

log() {
    printf '\n[%s] %s\n' "$1" "$2"
}

warn() {
    printf 'WARNING: %s\n' "$*" >&2
}

run_as_root() {
    if (( EUID == 0 )); then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        printf 'Root access is required to run: %q' "$1" >&2
        printf ' %q' "${@:2}" >&2
        printf '\n' >&2
        return 1
    fi
}

python_can_import() {
    python3 -c "import $1" >/dev/null 2>&1
}

clone_once() {
    local repository="$1"
    local destination="$2"
    shift 2
    if [[ -d "${destination}/.git" ]]; then
        printf 'Using existing source: %s\n' "${destination}"
        return
    fi
    mkdir -p "$(dirname "${destination}")"
    git clone --depth 1 "$@" "${repository}" "${destination}"
}

find_lcd_python_dir() {
    local candidate
    local candidates=(
        "${LCD_PYTHON_DIR:-}"
        "${USER_BASE}/LCD_Module_RPI_code/RaspberryPi/python"
        "${USER_BASE}/LCD_Module_code/LCD_Module_RPI_code/RaspberryPi/python"
        "${SETUP_SOURCE_DIR}/LCD_Module_RPI_code/RaspberryPi/python"
    )
    for candidate in "${candidates[@]}"; do
        if [[ -n "${candidate}" && -f "${candidate}/lib/LCD_2inch4.py" ]]; then
            printf '%s\n' "${candidate}"
            return 0
        fi
    done
    return 1
}

log "1/7" "Installing Debian prerequisites"
if [[ "${SKIP_APT:-0}" == "1" ]]; then
    printf 'Skipping apt packages (SKIP_APT=1).\n'
elif command -v apt-get >/dev/null 2>&1 && command -v dpkg-query >/dev/null 2>&1; then
    apt_packages=(
        alsa-utils
        build-essential
        cmake
        curl
        espeak
        ffmpeg
        fonts-noto-cjk
        ghostscript
        git
        i2c-tools
        libffi-dev
        libopenblas-dev
        libportaudio2
        libsndfile1
        libssl-dev
        ninja-build
        nodejs
        npm
        pkg-config
        portaudio19-dev
        python3-dev
        python3-pip
        python3-tk
        python3-venv
        sox
        swig
        unzip
    )
    missing_packages=()
    for package in "${apt_packages[@]}"; do
        if ! dpkg-query -W -f='${db:Status-Abbrev}' "${package}" 2>/dev/null | grep -q '^ii '; then
            missing_packages+=("${package}")
        fi
    done
    if ((${#missing_packages[@]})); then
        printf 'Installing missing packages: %s\n' "${missing_packages[*]}"
        run_as_root apt-get update
        run_as_root apt-get install -y "${missing_packages[@]}"
    else
        printf 'All Debian prerequisites are already installed.\n'
    fi
else
    warn "apt/dpkg not found; install the packages listed in setup.sh manually."
fi

log "2/7" "Checking SunFounder hardware libraries"
mkdir -p "${SETUP_SOURCE_DIR}"
ROBOT_HAT_SOURCE=""
if [[ -f "${USER_BASE}/robot-hat/install.py" ]]; then
    ROBOT_HAT_SOURCE="${USER_BASE}/robot-hat"
elif [[ -f "${SETUP_SOURCE_DIR}/robot-hat/install.py" ]]; then
    ROBOT_HAT_SOURCE="${SETUP_SOURCE_DIR}/robot-hat"
fi

if python_can_import robot_hat; then
    printf 'robot_hat is already importable.\n'
elif [[ "${SKIP_HARDWARE_LIBS:-0}" == "1" ]]; then
    warn "robot_hat is missing and SKIP_HARDWARE_LIBS=1."
else
    ROBOT_HAT_SOURCE="${SETUP_SOURCE_DIR}/robot-hat"
    clone_once https://github.com/sunfounder/robot-hat.git "${ROBOT_HAT_SOURCE}" -b 2.5.x
    (
        cd "${ROBOT_HAT_SOURCE}"
        run_as_root python3 install.py
    )
fi

if python_can_import vilib; then
    printf 'vilib is already importable.\n'
elif [[ "${SKIP_HARDWARE_LIBS:-0}" == "1" ]]; then
    warn "vilib is missing and SKIP_HARDWARE_LIBS=1."
else
    VILIB_SOURCE="${SETUP_SOURCE_DIR}/vilib"
    clone_once https://github.com/sunfounder/vilib.git "${VILIB_SOURCE}"
    (
        cd "${VILIB_SOURCE}"
        run_as_root python3 install.py
    )
fi

log "3/7" "Checking the Waveshare LCD driver"
if LCD_PYTHON_DIR_DETECTED="$(find_lcd_python_dir)"; then
    printf 'LCD driver found at %s\n' "${LCD_PYTHON_DIR_DETECTED}"
else
    LCD_SOURCE="${SETUP_SOURCE_DIR}/LCD_Module_RPI_code"
    clone_once https://github.com/waveshareteam/LCD_Module_RPI_code.git "${LCD_SOURCE}"
    LCD_PYTHON_DIR_DETECTED="${LCD_SOURCE}/RaspberryPi/python"
    if [[ ! -f "${LCD_PYTHON_DIR_DETECTED}/lib/LCD_2inch4.py" ]]; then
        warn "The downloaded LCD repository does not contain lib/LCD_2inch4.py."
    fi
fi

log "4/7" "Creating the Python environment and installing packages"
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    python3 -m venv --system-site-packages "${VENV_DIR}"
fi
"${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
"${VENV_DIR}/bin/python" -m pip install -r "${PROJECT_ROOT}/requirements-19v1.txt"
"${VENV_DIR}/bin/python" -m pip install -e "${PROJECT_ROOT}"

log "5/7" "Downloading speech models"
if [[ "${SKIP_MODELS:-0}" == "1" ]]; then
    printf 'Skipping model downloads (SKIP_MODELS=1).\n'
else
    if [[ -d "${VOSK_MODEL_DIR}" ]]; then
        printf 'Vosk wake model already exists at %s\n' "${VOSK_MODEL_DIR}"
    else
        temp_dir="$(mktemp -d)"
        trap 'rm -rf "${temp_dir}"' EXIT
        mkdir -p "$(dirname "${VOSK_MODEL_DIR}")"
        curl --fail --location --retry 3 \
            --output "${temp_dir}/vosk-model.zip" \
            https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
        unzip -q "${temp_dir}/vosk-model.zip" -d "$(dirname "${VOSK_MODEL_DIR}")"
        rm -rf "${temp_dir}"
        trap - EXIT
    fi

    printf 'Caching faster-whisper model: %s\n' "${WHISPER_MODEL}"
    WHISPER_MODEL="${WHISPER_MODEL}" "${VENV_DIR}/bin/python" - <<'PY'
import os
from faster_whisper import WhisperModel

WhisperModel(
    os.environ["WHISPER_MODEL"],
    device="cpu",
    compute_type="int8",
    cpu_threads=min(4, os.cpu_count() or 1),
    num_workers=1,
)
print("faster-whisper model is ready.")
PY

    printf 'Caching Piper voice: %s\n' "${PIPER_TTS_MODEL}"
    PIPER_TTS_MODEL="${PIPER_TTS_MODEL}" "${VENV_DIR}/bin/python" - <<'PY'
import os
from sunfounder_voice_assistant.tts import Piper

voice = Piper()
voice.set_model(os.environ["PIPER_TTS_MODEL"])
print("Piper voice is ready.")
PY
fi

log "6/7" "Configuring the Robot HAT I2S speaker"
if [[ "${CONFIGURE_I2S:-1}" == "0" ]]; then
    printf 'Skipping I2S configuration (CONFIGURE_I2S=0).\n'
elif [[ -r /proc/device-tree/model ]] && tr -d '\0' </proc/device-tree/model | grep -qi 'raspberry pi'; then
    if aplay -l 2>/dev/null | grep -qE 'sndrpihifiberry|sndrpigooglevoi'; then
        printf 'Robot HAT audio device is already active.\n'
    else
        boot_config=/boot/firmware/config.txt
        [[ -f "${boot_config}" ]] || boot_config=/boot/config.txt
        if [[ -f "${boot_config}" ]]; then
            if ! grep -qE '^[[:space:]]*dtoverlay=hifiberry-dac([,[:space:]]|$)' "${boot_config}"; then
                printf 'Enabling dtoverlay=hifiberry-dac in %s\n' "${boot_config}"
                printf '\n# PiCarXTalk / Robot HAT I2S speaker\ndtoverlay=hifiberry-dac\n' |
                    run_as_root tee -a "${boot_config}" >/dev/null
            fi
            if command -v dtoverlay >/dev/null 2>&1; then
                run_as_root dtoverlay hifiberry-dac >/dev/null 2>&1 || REBOOT_REQUIRED=1
            else
                REBOOT_REQUIRED=1
            fi
            sleep 2
            if ! aplay -l 2>/dev/null | grep -q 'sndrpihifiberry'; then
                REBOOT_REQUIRED=1
                warn "The I2S overlay is configured but is not active yet; reboot once after setup."
            fi
        else
            warn "Raspberry Pi boot config was not found; run robot-hat/i2samp.sh manually."
        fi
    fi
else
    printf 'Not a Raspberry Pi; skipping I2S boot configuration.\n'
fi

log "7/7" "Running preflight checks"
LCD_PYTHON_DIR="${LCD_PYTHON_DIR_DETECTED}" "${VENV_DIR}/bin/python" - <<'PY'
import importlib
import os
import sys

modules = ("edge_tts", "faster_whisper", "numpy", "PIL", "picarx", "requests", "spidev", "vosk")
for module in modules:
    importlib.import_module(module)

lcd_dir = os.environ["LCD_PYTHON_DIR"]
sys.path.append(lcd_dir)
from lib import LCD_2inch4  # noqa: F401

print("Python and LCD imports passed.")
PY

for device in /dev/i2c-1 /dev/spidev0.0; do
    if [[ -e "${device}" ]]; then
        printf 'Hardware bus ready: %s\n' "${device}"
    else
        warn "${device} is missing; enable I2C/SPI with raspi-config and reboot."
    fi
done

if arecord -l 2>/dev/null | grep -q '^card '; then
    printf 'Microphone capture device found.\n'
else
    warn "No ALSA microphone capture device was found."
fi

if aplay -l 2>/dev/null | grep -qE 'sndrpihifiberry|sndrpigooglevoi'; then
    printf 'Robot HAT playback device found.\n'
elif aplay -l 2>/dev/null | grep -q '^card '; then
    warn "Robot HAT playback is unavailable; another ALSA playback device will be used."
else
    warn "No ALSA playback device was found."
fi

if ! command -v codex >/dev/null 2>&1 && [[ "${SKIP_CODEX_INSTALL:-0}" != "1" ]]; then
    if command -v npm >/dev/null 2>&1; then
        printf 'Installing Codex CLI into %s\n' "${USER_BASE}/.local"
        mkdir -p "${USER_BASE}/.local"
        npm install --global --prefix "${USER_BASE}/.local" @openai/codex
        export PATH="${USER_BASE}/.local/bin:${PATH}"
        hash -r
    else
        warn "Codex CLI and npm are missing; install @openai/codex or use ./run_19v2.sh --ollama."
    fi
fi

if command -v codex >/dev/null 2>&1; then
    codex --version
    if ! codex login status; then
        warn "Codex is installed but not logged in. Run: codex login"
    fi
else
    warn "Codex CLI is missing. Install @openai/codex, run 'codex login', or use ./run_19v2.sh --ollama."
fi

printf '\nSetup complete.\n'
printf 'Run: cd %q && ./run_19v2.sh\n' "${EXAMPLE_DIR}"
printf 'The launcher detected LCD_PYTHON_DIR=%q\n' "${LCD_PYTHON_DIR_DETECTED}"
if (( REBOOT_REQUIRED )); then
    printf 'REBOOT REQUIRED: reboot the Raspberry Pi once, then run PiCarXTalk.\n'
fi



