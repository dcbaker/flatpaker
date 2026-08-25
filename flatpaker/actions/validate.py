# SPDX-License-Identifier: MIT
# Copyright © 2026 Dylan Baker

from __future__ import annotations

import sys
import typing
import warnings

from pydantic import ValidationError

from flatpaker.description import load_description

if typing.TYPE_CHECKING:

	from flatpaker.entry import ValidateConfig


def _emit_warning(warn: warnings.WarningMessage) -> str:
    if warn.category is DeprecationWarning:
        return f'Deprecation: {warn.message}'
    return warnings.formatwarning(
        warn.message, warn.category, warn.filename, warn.lineno, warn.line)


def validate(conf: ValidateConfig) -> bool:
    """Validate one or more toml files and print any errors"""
    warnings.simplefilter("default", DeprecationWarning)

    errors: list[ValidationError] = []
    ok = True

    with warnings.catch_warnings(record=True) as warns:
        for desc in conf.descriptions:
            try:
                load_description(desc)
            except ValidationError as e:
                errors.append(e)

        ok &= not bool(warns)
        for w in warns:
            print(_emit_warning(w), file=sys.stderr)

    ok &= not bool(errors)
    for err in errors:
        print(str(err), file=sys.stderr)

    return ok


