from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = ROOT / ".cache" / "noto-emoji" / "svg"
OUT_DIR = ROOT / "build" / "emoji"
DIST = ROOT / "dist"
TTF = DIST / "ttf"
NANOEMOJI = None

FLAG_RI = re.compile(r"emoji_u1f1[ef][0-9a-f]($|_)")
FLAG_TAG = re.compile(r"e00[0-9a-f]{2}")

PATCHES = {
    "emoji_u1f3f9.svg": "2D/svg/emoji_u1f3f9.svg",  # bow and arrow (had <mask>)
    "emoji_u1f4c6.svg": "2D/svg/emoji_u1f4c6.svg",  # tear-off calendar (had <text>)
}
PATCH_BASE = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main"


def ensure_patches() -> None:
    import urllib.request

    for name, rel in PATCHES.items():
        dst = SVG_DIR / name
        marker = dst.with_suffix(".patched")
        if marker.exists():
            continue
        log(f"  patch {name} <- current/{rel}")
        with urllib.request.urlopen(f"{PATCH_BASE}/{rel}") as r:
            dst.write_bytes(r.read())
        marker.write_text("patched\n", encoding="utf-8")


def log(msg: str) -> None:
    print(msg, flush=True)


def collect(limit: int | None = None) -> tuple[list[Path], list[Path]]:
    keep, dropped = [], []
    for p in sorted(SVG_DIR.glob("*.svg")):
        if FLAG_RI.search(p.stem) or FLAG_TAG.search(p.stem):
            dropped.append(p)
        else:
            keep.append(p)
    if limit:
        pick = keep[: limit // 2] + keep[-limit // 2 :]
        keep = pick
    return keep, dropped


def toml_body(srcs: list[Path], family: str, output: str) -> str:
    lines = [
        f'family = "{family}"',
        f'output_file = "{output}"',
        'color_format = "glyf_colr_1"',
        "clipbox_quantization = 32",
        "",
        "[axis.wght]",
        'name = "Weight"',
        "default = 400",
        "",
        "[master.regular]",
        'style_name = "Regular"',
        "srcs = [",
    ]
    for p in srcs:
        lines.append(f'    "{p.as_posix()}",')
    lines += ["]", ""]
    lines += ["[master.regular.position]", "wght = 400", ""]
    return "\n".join(lines)


ASCII_KEYCAP_BASES = {0x20, 0x23, 0x2A, *range(0x30, 0x3A)}


def drop_keycap_cmap(font: TTFont) -> int:
    removed = 0
    for table in font["cmap"].tables:
        if not table.isUnicode():
            continue
        for cp in ASCII_KEYCAP_BASES:
            if cp in table.cmap:
                del table.cmap[cp]
                removed += 1
    return removed


def rewrite_names(path: Path) -> None:
    from meta import apply, upstream_parts

    parts = upstream_parts()
    f = TTFont(path)
    apply(
        f,
        family="YumeSans Emoji",
        ps_name="YumeSansEmoji-Regular",
        parts=[parts["noto"]],
    )
    if "DSIG" in f:
        del f["DSIG"]
    n = drop_keycap_cmap(f)
    log(f"    dropped {n} ASCII keycap cmap entries (space/#/*/0-9)")
    f.save(path)


def main() -> None:
    limit = None
    config_only = False
    args = sys.argv[1:]
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    config_only = "--config-only" in args

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ensure_patches()
    keep, dropped = collect(limit)
    log(f"[emoji] svg sources: {len(keep)} kept, {len(dropped)} flag(s) dropped")
    for d in dropped:
        log(f"    - {d.name}")

    out_name = "YumeSansEmoji-Regular.ttf"
    toml = OUT_DIR / "emoji.toml"
    toml.write_text(toml_body(keep, "YumeSans Emoji", out_name), encoding="utf-8")
    log(f"  wrote {toml.relative_to(ROOT)}")
    if config_only:
        return

    venv = ROOT / ".venv"
    nanoemoji = venv / "Scripts" / "nanoemoji.exe"
    if not nanoemoji.exists():
        nanoemoji = venv / "bin" / "nanoemoji"
    if not nanoemoji.exists():
        raise SystemExit(f"nanoemoji not found in {venv}")

    env = dict(**__import__("os").environ)
    script_dir = nanoemoji.parent
    env["PATH"] = str(script_dir) + __import__("os").pathsep + env.get("PATH", "")
    log(f"  $ {nanoemoji} {toml.name}")
    r = subprocess.run(
        [str(nanoemoji), str(toml)],
        cwd=OUT_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        log((r.stdout or "")[-4000:])
        log((r.stderr or "")[-4000:])
        raise SystemExit(f"nanoemoji failed ({r.returncode})")

    produced = OUT_DIR / "build" / out_name
    if not produced.exists():
        produced = OUT_DIR / out_name
    if not produced.exists():
        raise SystemExit(f"nanoemoji produced nothing at {produced}")

    rewrite_names(produced)
    TTF.mkdir(parents=True, exist_ok=True)
    target = TTF / out_name
    target.write_bytes(produced.read_bytes())
    log(f"  -> dist/ttf/{out_name} ({target.stat().st_size / 1048576:.2f} MB)")


if __name__ == "__main__":
    main()
