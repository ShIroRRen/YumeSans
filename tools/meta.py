from __future__ import annotations

import calendar
import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from fontTools.misc.timeTools import epoch_diff, timestampNow
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
VENDOR = "OpenYume"
TAG = "OYUME"
COPYRIGHT = "Copyright 2026 OpenYume"
SAMPLE = "Hello 世界 -> 😄"

UFL_URL = "https://canonical.com/legal/font-licence"
OFL_URL = "https://openfontlicense.org"
VENDOR_URL = "https://openyu.me"

_VER_RE = re.compile(r"(\d+(?:\.\d+)+)")


@dataclass
class Part:
    name: str
    version: str
    license: str
    license_url: str
    trademark: str | None
    created: int


def project_version() -> tuple[str, float]:
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    raw = pkg.get("version", "0.0.0")
    parts = raw.split(".")
    revision = float(f"{parts[0]}.{parts[1] if len(parts) > 1 else 0}")
    return f"{revision:.3f}", revision


def version_of(font: TTFont) -> str:
    for nid in (5, 3):
        v = font["name"].getDebugName(nid)
        if not v:
            continue
        m = _VER_RE.search(v)
        if m:
            return m.group(1)
    return "unknown"


def part_from_font(
    path: Path,
    *,
    license_: str,
    license_url: str,
    name: str | None = None,
    keep_trademark: bool = False,
    created: int | None = None,
) -> Part:
    font = TTFont(path, lazy=True)
    try:
        family = (
            name
            or font["name"].getDebugName(16)
            or font["name"].getDebugName(1)
            or path.stem
        )
        ver = version_of(font)
        tm = font["name"].getDebugName(7) if keep_trademark else None
        made = created if created is not None else font["head"].created + epoch_diff
    finally:
        font.close()
    return Part(
        name=family.strip(),
        version=ver,
        license=license_,
        license_url=license_url,
        trademark=(tm.strip() if tm else None),
        created=int(made),
    )


def describe(parts: list[Part]) -> str:
    return "Based on " + ", ".join(f"{p.name} {p.version}" for p in parts) + "."


def license_text(parts: list[Part]) -> str:
    groups: dict[str, list[str]] = {}
    for p in parts:
        groups.setdefault(p.license, []).append(p.name)
    return " ".join(f"{lic} ({', '.join(names)})." for lic, names in groups.items())


def license_urls(parts: list[Part]) -> str:
    seen: list[str] = []
    for p in parts:
        if p.license_url and p.license_url not in seen:
            seen.append(p.license_url)
    return " ".join(seen)


def trademarks(parts: list[Part]) -> str | None:
    seen: list[str] = []
    for p in parts:
        if p.trademark and p.trademark not in seen:
            seen.append(p.trademark)
    return " ".join(seen) if seen else None


def apply(
    font: TTFont,
    *,
    family: str,
    ps_name: str,
    parts: list[Part],
    subfamily: str = "Regular",
    created: int | None = None,
    modified: int | None = None,
) -> None:
    ver_str, revision = project_version()

    font["head"].fontRevision = revision
    created_unix = created if created is not None else min(p.created for p in parts)
    modified_unix = (
        modified if modified is not None else int(timestampNow() + epoch_diff)
    )
    font["head"].created = created_unix - epoch_diff  # unix -> 1904 基准
    font["head"].modified = modified_unix - epoch_diff

    if "OS/2" in font:
        font["OS/2"].achVendID = ""

    records: dict[int, str] = {
        0: COPYRIGHT,
        1: family,
        2: subfamily,
        3: f"{ver_str};{TAG};{ps_name}",
        4: f"{family} {subfamily}",
        5: f"Version {ver_str}",
        6: ps_name,
        8: VENDOR,
        10: describe(parts),
        11: VENDOR_URL,
        13: license_text(parts),
        14: license_urls(parts),
        16: family,
        17: subfamily,
        19: SAMPLE,
    }
    tm = trademarks(parts)
    if tm:
        records[7] = tm

    name = font["name"]
    name.names = []
    for name_id, value in records.items():
        name.setName(str(value), name_id, 3, 1, 0x409)
    for name_id in (1, 2, 4, 6, 10, 13, 16, 17, 19):
        if name_id in records:
            name.setName(str(records[name_id]), name_id, 3, 10, 0x409)


SRC = ROOT / ".cache"


def noto_part() -> Part:
    txt = ""

    def namerecord(nid: int) -> str | None:
        m = re.search(
            rf'<namerecord nameID="{nid}" platformID="3" platEncID="1" langID="0x409">\s*(.*?)\s*</namerecord>',
            txt,
            re.S,
        )
        return m.group(1).strip() if m else None

    family = namerecord(1) or "Noto Color Emoji"
    ver_raw = namerecord(5) or ""
    m = _VER_RE.search(ver_raw)
    version = m.group(1) if m else "unknown"
    tm = namerecord(7)

    cm = re.search(r'<created value="(.*?)"', txt)
    created = (
        int(calendar.timegm(time.strptime(cm.group(1), "%a %b %d %H:%M:%S %Y")))
        if cm
        else 0
    )

    return Part(
        name=family,
        version=version,
        license="OFL 1.1",
        license_url=OFL_URL,
        trademark=(tm.strip() if tm else None),
        created=created,
    )


def upstream_parts() -> dict[str, Part]:
    return {
        "ubuntu": part_from_font(
            SRC / "UbuntuSans-Regular.ttf",
            license_="UFL 1.0",
            license_url=UFL_URL,
            keep_trademark=True,
        ),
        "chill": part_from_font(
            SRC / "ChillRoundF-Regular.ttf",
            license_="OFL 1.1",
            license_url=OFL_URL,
            keep_trademark=False,
        ),
        "fusion": part_from_font(
            SRC / "JetBrainsMapleMono-Regular.ttf",
            license_="OFL 1.1",
            license_url=OFL_URL,
            keep_trademark=False,
        ),
        "noto": noto_part(),
    }
