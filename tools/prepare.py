from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".cache"
BUILD = ROOT / "build"
DIST = ROOT / "dist"
TTF = DIST / "ttf"
for dir in (BUILD, DIST, TTF):
    dir.mkdir(parents=True, exist_ok=True)


def best_cmap(path: Path) -> dict[int, str]:
    with TTFont(path, lazy=True) as f:
        return f.getBestCmap()


def write_unicodes(cps, path: Path) -> Path:
    path.write_text("\n".join(f"{cp:04X}" for cp in sorted(cps)), encoding="utf-8")
    return path


def hb_subset(
    src: Path, dst: Path, unicodes_file: Path, no_hinting: bool = True
) -> None:
    cmd = [
        "hb-subset",
        str(src),
        f"--unicodes-file={unicodes_file}",
        f"--output-file={dst}",
        "--glyph-names",
        "--layout-features=*",
        "--name-IDs=*",
        "--name-languages=*",
        "--notdef-outline",
    ]
    if no_hinting:
        cmd.append("--no-hinting")
    print("  $ hb-subset " + src.name + " -> " + dst.name)
    ret = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if ret.returncode != 0:
        raise RuntimeError(f"hb-subset failed: {(ret.stderr or '')[:2000]}")


def drop_tables(font: TTFont, tags: list[str]) -> None:
    for t in tags:
        if t in font:
            del font[t]


def finish(font: TTFont, out: Path) -> None:
    font.save(out)
    print(
        f"  -> {out.relative_to(ROOT)}  ({out.stat().st_size / 1048576:.2f} MB, "
        f"{font['maxp'].numGlyphs} glyphs, upm {font['head'].unitsPerEm})"
    )


def build_latin() -> None:
    from meta import apply, upstream_parts

    print("[latin] Ubuntu Sans -> YumeSans Latin")
    parts = upstream_parts()
    font = TTFont(SRC / "UbuntuSans-Regular.ttf")
    apply(
        font,
        family="YumeSans Latin",
        ps_name="YumeSansLatin-Regular",
        parts=[parts["ubuntu"]],
    )
    drop_tables(font, ["DSIG"])
    finish(font, TTF / "YumeSansLatin-Regular.ttf")


def build_cjk() -> None:
    from meta import apply, upstream_parts

    print("[CJK] ChillRoundF -> YumeSans CJK")
    parts = upstream_parts()
    src = SRC / "ChillRoundF-Regular.ttf"
    latin_cps = set(best_cmap(SRC / "UbuntuSans-Regular.ttf"))
    all_cps = set(best_cmap(src))
    keep = sorted(all_cps - latin_cps)
    print(
        f"  keep {len(keep)} cps (dropped {len(all_cps & latin_cps)} shared with Latin)"
    )

    ufile = write_unicodes(keep, BUILD / "cjk-unicodes.txt")
    sub = BUILD / "cjk-subset.ttf"
    hb_subset(src, sub, ufile, no_hinting=True)

    font = TTFont(sub)
    apply(
        font,
        family="YumeSans CJK",
        ps_name="YumeSansCJK-Regular",
        parts=[parts["chill"]],
    )
    drop_tables(font, ["DSIG"])

    upm = font["head"].unitsPerEm
    asc, desc = round(940 / 1000 * upm), round(-260 / 1000 * upm)
    font["hhea"].ascent, font["hhea"].descent, font["hhea"].lineGap = asc, desc, 0
    os2 = font["OS/2"]
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = asc, desc, 0
    os2.fsSelection |= 0b10000000  # USE_TYPO_METRICS
    print(f"    vertical metrics -> {asc}/{desc}")
    finish(font, TTF / "YumeSansCJK-Regular.ttf")


def build_mono() -> None:
    from meta import apply, upstream_parts

    print("[mono] JetBrains Maple Mono (NF+NR) -> YumeSans Mono")
    parts = upstream_parts()
    font = TTFont(SRC / "JetBrainsMapleMono-Regular.ttf")
    cm = font.getBestCmap()
    print(
        f"  cmap {len(cm)}, cjk {sum(1 for c in cm if 0x4E00 <= c <= 0x9FFF)}, "
        f"pua {sum(1 for c in cm if 0xE000 <= c <= 0xF8FF)}"
    )

    apply(
        font,
        family="YumeSans Mono",
        ps_name="YumeSansMono-Regular",
        parts=[parts["fusion"]],
    )
    drop_tables(font, ["DSIG", "FFTM"])
    finish(font, TTF / "YumeSansMono-Regular.ttf")


def main() -> None:
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("latin", "all"):
        build_latin()
    if what in ("cjk", "all"):
        build_cjk()
    if what in ("mono", "all"):
        build_mono()


if __name__ == "__main__":
    main()
