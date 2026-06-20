from __future__ import annotations

import ast
import json
from typing import Any


def frontmatter(data: dict[str, Any]) -> str:
    lines = ["---"]
    for key in sorted(data):
        value = data[key]
        if isinstance(value, (dict, list)):
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif value is None:
            lines.append(f"{key}: null")
        else:
            text = str(value).replace('"', '\\"')
            lines.append(f'{key}: "{text}"')
    lines.append("---")
    return "\n".join(lines) + "\n"


def note(data: dict[str, Any], body: str) -> str:
    return frontmatter(data) + "\n" + body.rstrip() + "\n"


class FrontmatterError(ValueError):
    pass


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        raise FrontmatterError("frontmatter opening marker has no closing marker")
    raw = text[4:end].splitlines()
    data: dict[str, object] = {}
    for line in raw:
        if ":" in line:
            key, value = line.split(":", 1)
            clean = value.strip()
            if clean.startswith("[") or clean.startswith("{"):
                try:
                    data[key.strip()] = json.loads(clean)
                except json.JSONDecodeError:
                    data[key.strip()] = ast.literal_eval(clean)
            else:
                data[key.strip()] = clean.strip('"')
    return data, text[end + 5 :]
