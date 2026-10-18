"""Read local configuration without executing shell commands."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shlex


ROOT = Path(__file__).resolve().parents[1]
VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def read_environment(path: Path, inherited=None) -> dict[str, str]:
    inherited = dict(os.environ if inherited is None else inherited)
    context = dict(inherited)
    context.setdefault("LDWM_ROOT", str(ROOT))
    values = {}
    if not path.is_file():
        return values
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        key, separator, raw = line.partition("=")
        key = key.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"Invalid environment assignment at {path.name}:{number}")
        try:
            tokens = shlex.split(raw, comments=True, posix=True)
        except ValueError as exc:
            raise ValueError(f"Invalid quoting at {path.name}:{number}") from exc
        if len(tokens) > 1:
            raise ValueError(f"Quote values containing spaces at {path.name}:{number}")
        value = tokens[0] if tokens else ""

        def expand(match):
            name = match.group(1)
            if name not in context:
                raise ValueError(f"Undefined variable {name} at {path.name}:{number}")
            return context[name]

        value = VARIABLE.sub(expand, value)
        values[key] = value
        if key not in inherited:
            context[key] = value
    return values


def load_environment(path: Path | None = None) -> dict[str, str]:
    values = read_environment(path or ROOT / ".env.gpu")
    for key, value in values.items():
        os.environ.setdefault(key, value)
    return values
