# SPDX-License-Identifier: MIT
# Copyright © 2026 Dylan Baker

"""Dump JSON schema from pydantic models."""

from __future__ import annotations

import json
import pathlib
import sys

from flatpaker.description import Description


def dump_schema(path: pathlib.Path) -> bool:
    """Dump JSON schmea from Pydantic model."""
    # TODO: there are a load of exceptions that could be generated here and need
    # to be caught and turned into failures
    try:
        # Ensure the directory exists before attempting to write the file
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w') as f:
            json.dump(Description.model_json_schema(by_alias=True), f, indent=4)
    except PermissionError:
        print(f'Error: Failed to open {path!s} for writing', file=sys.stderr)
    else:
        return True
    return False
