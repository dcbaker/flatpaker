set -exo pipefail

apt update -y

apt install -y \
    python3 \
    appstream \
    flatpak-builder \
    python3-pip \
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
