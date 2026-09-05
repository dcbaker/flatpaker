set -exo pipefail

pip install --break-system-packages \
    flit \
    mypy \
    ruff \
    tomlkit \
    pydantic \
    ;
