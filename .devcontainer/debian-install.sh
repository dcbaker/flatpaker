set -exo pipefail

apt update -y

apt install -y \
    python3 \
    appstream \
    flatpak-builder \
    python3-pip \
    rustup \
    libglib2.0-dev \
    libostree-dev \
    ;

apt clean -y

pip install --break-system-packages \
    flit \
    mypy \
    packaging \
    requirements-parser \
    ruff \
    tomlkit \
    pydantic \
    ;

rustup default stable

cargo install --git https://github.com/flatpak/flat-manager flat-manager-client

flatpak remote-add --if-not-exists --user flathub https://flathub.org/repo/flathub.flatpakrepo
