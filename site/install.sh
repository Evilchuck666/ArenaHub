#!/bin/sh
# Install ArenaHub on GNU/Linux or macOS with one command:
#
#   curl -fsSL https://evilchuck666.github.io/ArenaHub/install.sh | sh
#   wget -qO- https://evilchuck666.github.io/ArenaHub/install.sh | sh
#
# What it installs:
#   GNU/Linux, Arch and derivatives  the arenahub-bin AUR package, with an AUR helper
#                                    (paru, yay, pikaur, trizen) or with makepkg
#   GNU/Linux, other distributions   the ArenaHub package from PyPI with uv (and a
#                                    uv-managed Python), plus an application menu entry
#   macOS (Intel or Apple Silicon)   the release's executable as ~/Applications/ArenaHub.app
#
# Run it again to update. Windows uses install.ps1 instead.

set -eu

REPO="Evilchuck666/ArenaHub"
RELEASES="https://github.com/$REPO/releases"
AUR_PACKAGE="arenahub-bin"
AUR_REPOSITORY="https://aur.archlinux.org/$AUR_PACKAGE.git"
PYPI_PACKAGE="ArenaHub"
PYTHON_VERSION="3.13"
UV_INSTALLER="https://astral.sh/uv/install.sh"
MACOS_APP="$HOME/Applications/ArenaHub.app"

WORKDIR=""

# --------------------------------------------------------------------------------------
# Common helpers
# --------------------------------------------------------------------------------------

say() {
    printf '==> %s\n' "$*"
}

warn() {
    printf 'warning: %s\n' "$*" >&2
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

has() {
    command -v "$1" >/dev/null 2>&1
}

# download URL DEST: save a file with curl or wget, whichever the system has.
download() {
    if has curl; then
        curl -fsSL --retry 3 -o "$2" "$1"
    elif has wget; then
        wget -q -O "$2" "$1"
    else
        die "Install curl or wget first."
    fi
}

# fetch_text URL: print a small text resource.
fetch_text() {
    if has curl; then
        curl -fsSL --retry 3 "$1"
    elif has wget; then
        wget -q -O - "$1"
    else
        die "Install curl or wget first."
    fi
}

# latest_version: the version of the latest GitHub release, without the v.
# releases/latest redirects to releases/tag/vX.Y.Z. Unlike the GitHub API, that has no
# per-IP limit for anonymous requests, which shared IPs (offices, CI) run into.
latest_version() {
    if has curl; then
        tag_url=$(curl -fsSLI -o /dev/null -w '%{url_effective}' "$RELEASES/latest" 2>/dev/null) ||
            tag_url=""
        case "$tag_url" in
            */releases/tag/*)
                printf '%s' "${tag_url##*/releases/tag/}" | sed 's/^v//'
                return 0
                ;;
        esac
    fi
    fetch_text "https://api.github.com/repos/$REPO/releases/latest" |
        sed -n 's/^[[:space:]]*"tag_name":[[:space:]]*"v\{0,1\}\([^"]*\)".*/\1/p' |
        head -n 1
}

make_workdir() {
    WORKDIR=$(mktemp -d 2>/dev/null || mktemp -d -t arenahub)
    trap 'rm -rf "$WORKDIR"' EXIT
    trap 'exit 130' INT TERM
}

# When this script comes through a pipe, its stdin is the script itself, so commands
# that ask questions read the terminal instead. Without one (CI), they must not ask.
tty_available() {
    # A subshell: a failed redirection must not stop this script.
    (true </dev/tty) 2>/dev/null
}

# run_interactive COMMAND...: run a command that may ask the user something.
run_interactive() {
    if tty_available; then
        "$@" </dev/tty
    else
        "$@"
    fi
}

# confirm_flag: --noconfirm for pacman-style tools when nobody can answer.
confirm_flag() {
    if tty_available; then
        printf ''
    else
        printf '%s' '--noconfirm'
    fi
}

os_release_value() {
    [ -r /etc/os-release ] || return 0
    # shellcheck disable=SC1091
    (. /etc/os-release && eval "printf '%s' \"\${$1:-}\"")
}

# --------------------------------------------------------------------------------------
# GNU/Linux: Arch Linux and derivatives (AUR package)
# --------------------------------------------------------------------------------------

linux_is_arch_based() {
    for word in $(os_release_value ID) $(os_release_value ID_LIKE); do
        [ "$word" = "arch" ] && return 0
    done
    has pacman && has makepkg
}

arch_find_aur_helper() {
    for helper in paru yay pikaur trizen; do
        if has "$helper"; then
            printf '%s' "$helper"
            return 0
        fi
    done
    return 1
}

arch_install_with_helper() {
    say "Installing $AUR_PACKAGE from the AUR with $1"
    # shellcheck disable=SC2046  # an empty flag must vanish
    run_interactive "$1" -S --needed $(confirm_flag) "$AUR_PACKAGE"
}

arch_install_with_makepkg() {
    say "No AUR helper found: building $AUR_PACKAGE with makepkg"
    if ! has makepkg || ! has fakeroot || ! has git; then
        say "Installing base-devel and git (makepkg and the AUR need them)"
        # shellcheck disable=SC2046
        run_interactive sudo pacman -S --needed $(confirm_flag) base-devel git
    fi
    git clone --quiet --depth 1 "$AUR_REPOSITORY" "$WORKDIR/$AUR_PACKAGE"
    # makepkg checks the release's checksums from the AUR PKGBUILD, installs the
    # dependencies with pacman and then the package itself.
    # shellcheck disable=SC2046
    (cd "$WORKDIR/$AUR_PACKAGE" && run_interactive makepkg -si $(confirm_flag))
}

arch_install() {
    if [ "$(id -u)" -eq 0 ]; then
        die "Run this as your normal user, not root: it uses sudo when it needs to."
    fi
    if helper=$(arch_find_aur_helper); then
        arch_install_with_helper "$helper"
    else
        arch_install_with_makepkg
    fi
    pacman -Q "$AUR_PACKAGE" >/dev/null 2>&1 || die "$AUR_PACKAGE did not get installed."
    say "Installed $(pacman -Q "$AUR_PACKAGE"), with its application menu entry and icon."
    say "Open ArenaHub from your application menu, or run: arenahub"
    say "To uninstall: sudo pacman -R $AUR_PACKAGE"
}

# --------------------------------------------------------------------------------------
# GNU/Linux: other distributions (PyPI package with uv)
# --------------------------------------------------------------------------------------

UV=""

linux_ensure_uv() {
    if has uv; then
        UV=$(command -v uv)
    elif [ -x "$HOME/.local/bin/uv" ]; then
        UV="$HOME/.local/bin/uv"
    else
        say "Installing uv (https://docs.astral.sh/uv/) to run ArenaHub on Python $PYTHON_VERSION"
        download "$UV_INSTALLER" "$WORKDIR/uv-install.sh"
        sh "$WORKDIR/uv-install.sh" --quiet </dev/null
        for candidate in "${XDG_BIN_HOME:-}/uv" "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
            if [ -x "$candidate" ]; then
                UV="$candidate"
                break
            fi
        done
        [ -n "$UV" ] || die "uv was installed, but its executable was not found."
    fi
}

linux_install_from_pypi() {
    say "Installing $PYPI_PACKAGE from PyPI with uv"
    "$UV" tool install --upgrade --python "$PYTHON_VERSION" "$PYPI_PACKAGE"
}

# The icon ships inside the package; ask the installed ArenaHub where it is.
linux_package_icon() {
    tool_python="$("$UV" tool dir)/arenahub/bin/python"
    [ -x "$tool_python" ] || return 1
    "$tool_python" -I -c \
        "from arenahub.core import paths; print(paths.resource('icons', 'arenahub.svg'))"
}

# Quote a path for the Exec key of a .desktop file.
linux_desktop_quote() {
    printf '"%s"' "$(printf '%s' "$1" | sed 's/[\\"`$]/\\&/g')"
}

linux_create_menu_entry() {
    data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
    executable="$("$UV" tool dir --bin)/arenahub"
    [ -x "$executable" ] || die "$executable is missing after the installation."

    icon_dir="$data_home/icons/hicolor/scalable/apps"
    mkdir -p "$icon_dir" "$data_home/applications"
    if icon=$(linux_package_icon) && [ -f "$icon" ]; then
        cp "$icon" "$icon_dir/arenahub.svg"
    else
        warn "Could not find ArenaHub's icon; the menu entry will use a generic one."
    fi

    cat >"$data_home/applications/arenahub.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ArenaHub
GenericName=Quake III Arena launcher
Comment=Install and play Quake III Arena, Team Arena and classic mods
TryExec=$executable
Exec=$(linux_desktop_quote "$executable")
Icon=arenahub
Terminal=false
Categories=Game;ActionGame;
Keywords=quake;quake3;quake3e;arena;cpma;osp;steam;
EOF

    if has update-desktop-database; then
        update-desktop-database -q "$data_home/applications" 2>/dev/null || true
    fi
    if has gtk-update-icon-cache && [ -f "$data_home/icons/hicolor/index.theme" ]; then
        gtk-update-icon-cache -q -t "$data_home/icons/hicolor" 2>/dev/null || true
    fi
    say "Added ArenaHub to your application menu."
}

linux_has_library() {
    for ldconfig in ldconfig /sbin/ldconfig /usr/sbin/ldconfig; do
        if has "$ldconfig"; then
            "$ldconfig" -p 2>/dev/null | grep -q "$1" && return 0
            return 1
        fi
    done
    return 0 # can't tell, so don't warn
}

# Quake3e needs SDL2 and Qt's X11 support needs libxcb-cursor; the PyPI package
# can't install them, so only point them out.
linux_check_libraries() {
    missing_sdl=""
    missing_xcb=""
    linux_has_library libSDL2-2.0.so.0 || missing_sdl=1
    linux_has_library libxcb-cursor.so.0 || missing_xcb=1
    [ -n "$missing_sdl$missing_xcb" ] || return 0

    family="$(os_release_value ID) $(os_release_value ID_LIKE)"
    case " $family " in
        *" debian "* | *" ubuntu "*)
            command="sudo apt install${missing_sdl:+ libsdl2-2.0-0}${missing_xcb:+ libxcb-cursor0}" ;;
        *" fedora "* | *" rhel "*)
            command="sudo dnf install${missing_sdl:+ SDL2}${missing_xcb:+ xcb-util-cursor}" ;;
        *" suse "* | *" opensuse "*)
            command="sudo zypper install${missing_sdl:+ libSDL2-2_0-0}${missing_xcb:+ libxcb-cursor0}" ;;
        *)
            command="" ;;
    esac
    [ -z "$missing_sdl" ] || warn "SDL2 is missing; Quake3e needs it to start the games."
    [ -z "$missing_xcb" ] || warn "libxcb-cursor is missing; Qt needs it to open ArenaHub on X11."
    if [ -n "$command" ]; then
        warn "Install it with: $command"
    else
        warn "Install it with your distribution's package manager."
    fi
}

linux_install_other() {
    linux_ensure_uv
    linux_install_from_pypi
    linux_create_menu_entry
    linux_check_libraries
    say "Open ArenaHub from your application menu, or run: $("$UV" tool dir --bin)/arenahub"
    say "To uninstall: $UV tool uninstall $PYPI_PACKAGE && rm -f" \
        "${XDG_DATA_HOME:-$HOME/.local/share}/applications/arenahub.desktop" \
        "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps/arenahub.svg"
}

# --------------------------------------------------------------------------------------
# macOS (Intel or Apple Silicon)
# --------------------------------------------------------------------------------------

# arm64 or x64. A shell running under Rosetta reports x86_64 on Apple Silicon.
macos_arch() {
    if [ "$(uname -m)" = "arm64" ] ||
        [ "$(sysctl -n sysctl.proc_translated 2>/dev/null || echo 0)" = "1" ]; then
        printf 'arm64'
    else
        printf 'x64'
    fi
}

# macos_download_release ARCH: download, verify and extract the release package.
macos_download_release() {
    package="ArenaHub-macos-$1.zip"
    say "Downloading $package"
    download "$RELEASES/latest/download/$package" "$WORKDIR/$package"
    download "$RELEASES/latest/download/SHA256SUMS.txt" "$WORKDIR/SHA256SUMS.txt"

    expected=$(awk -v name="$package" '$2 == name { print $1 }' "$WORKDIR/SHA256SUMS.txt")
    actual=$(shasum -a 256 "$WORKDIR/$package" | awk '{ print $1 }')
    [ -n "$expected" ] || die "SHA256SUMS.txt has no checksum for $package."
    [ "$expected" = "$actual" ] || die "Checksum mismatch for $package; try again."

    ditto -x -k "$WORKDIR/$package" "$WORKDIR/extracted"
    [ -f "$WORKDIR/extracted/ArenaHub" ] || die "$package does not contain ArenaHub."
}

# macos_create_app VERSION: wrap the executable in an .app bundle, so it shows up in
# Launchpad, Spotlight and Finder like any other application.
macos_create_app() {
    say "Installing $MACOS_APP"
    rm -rf "$MACOS_APP"
    mkdir -p "$MACOS_APP/Contents/MacOS" "$MACOS_APP/Contents/Resources"
    mv "$WORKDIR/extracted/ArenaHub" "$MACOS_APP/Contents/MacOS/ArenaHub"
    chmod 755 "$MACOS_APP/Contents/MacOS/ArenaHub"
    if ! download "https://raw.githubusercontent.com/$REPO/v$1/assets/icons/arenahub.icns" \
        "$MACOS_APP/Contents/Resources/arenahub.icns"; then
        warn "Could not download ArenaHub's icon; the app will use a generic one."
    fi

    cat >"$MACOS_APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>ArenaHub</string>
    <key>CFBundleDisplayName</key>
    <string>ArenaHub</string>
    <key>CFBundleIdentifier</key>
    <string>io.github.evilchuck666.arenahub</string>
    <key>CFBundleExecutable</key>
    <string>ArenaHub</string>
    <key>CFBundleIconFile</key>
    <string>arenahub</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$1</string>
    <key>CFBundleVersion</key>
    <string>$1</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.action-games</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

    # Downloaded with curl, it carries no quarantine flag; clear any just in case.
    xattr -cr "$MACOS_APP" 2>/dev/null || true
    lsregister="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
    if [ -x "$lsregister" ]; then
        "$lsregister" -f "$MACOS_APP" 2>/dev/null || true
    fi
}

macos_install() {
    arch=$(macos_arch)
    version=$(latest_version) || true
    [ -n "$version" ] || die "Could not find the latest ArenaHub release."
    macos_download_release "$arch"
    macos_create_app "$version"
    say "Installed ArenaHub $version ($arch)."
    say "Open it from Launchpad, Spotlight or $MACOS_APP"
    say "To uninstall: rm -rf \"$MACOS_APP\""
}

# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------

main() {
    make_workdir
    case "$(uname -s)" in
        Linux)
            if linux_is_arch_based; then
                arch_install
            else
                linux_install_other
            fi
            ;;
        Darwin)
            macos_install
            ;;
        *)
            die "This script supports GNU/Linux and macOS. On Windows, run in PowerShell:" \
                "irm https://evilchuck666.github.io/ArenaHub/install.ps1 | iex"
            ;;
    esac
}

main "$@"
