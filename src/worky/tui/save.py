"""serializacion del estado de la consola a un archivo .worky."""

from __future__ import annotations

import json

from worky.tui.session import SessionSpec


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_workspace(specs: list[SessionSpec], header: str | None = None) -> str:
    lines: list[str] = [f"// {header or 'workspace generado por worky --cli'}", ""]
    for spec in specs:
        lines.append(f"in {_quote(spec.cwd)} {{")
        lines.append(f"  run {_quote(spec.name)} {{")
        lines.append("    os: all {")
        if spec.raw:
            for raw_line in spec.raw.splitlines():
                lines.append(f"      {raw_line}".rstrip())
        elif spec.command:
            lines.append(f"      /shell {spec.command}".rstrip())
        else:
            lines.append("      /shell")
        lines.append("    }")
        lines.append("  }")
        lines.append("}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
