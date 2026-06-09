from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


@dataclass(frozen=True)
class ReasonCodeMap:
    aliases: dict[str, str]
    warn_unmapped: bool = True

    def normalize(self, reason: str) -> tuple[str, bool]:
        cleaned = reason.strip()
        if not cleaned:
            return "unspecified", False

        canonical = self.aliases.get(_reason_key(cleaned))
        if canonical:
            return canonical, True
        return cleaned, False


def read_reason_code_map(source: str | Path | TextIO) -> ReasonCodeMap:
    close_after = False
    if isinstance(source, (str, Path)):
        handle = Path(source).open("r", encoding="utf-8")
        close_after = True
    else:
        handle = source

    try:
        data = json.load(handle)
    finally:
        if close_after:
            handle.close()

    if not isinstance(data, dict):
        raise ValueError("Reason code map must be a JSON object.")

    warn_unmapped = bool(data.get("warn_unmapped", True))
    categories = data.get("categories")
    if not isinstance(categories, list) or not categories:
        raise ValueError("Reason code map must include a non-empty categories list.")

    aliases: dict[str, str] = {}
    for index, category in enumerate(categories):
        if not isinstance(category, dict):
            raise ValueError(f"categories[{index}] must be an object.")
        canonical = str(category.get("canonical") or category.get("reason") or "").strip()
        if not canonical:
            raise ValueError(f"categories[{index}] must include canonical.")

        raw_aliases = category.get("aliases", [])
        if not isinstance(raw_aliases, list):
            raise ValueError(f"categories[{index}].aliases must be a list.")

        values = [canonical, *raw_aliases]
        for value in values:
            alias = str(value).strip()
            if not alias:
                continue
            key = _reason_key(alias)
            existing = aliases.get(key)
            if existing and existing != canonical:
                raise ValueError(
                    f"Reason alias {alias!r} maps to both {existing!r} and {canonical!r}."
                )
            aliases[key] = canonical

    return ReasonCodeMap(aliases=aliases, warn_unmapped=warn_unmapped)


def _reason_key(reason: str) -> str:
    return re.sub(r"[\s_-]+", " ", reason.strip().lower())
