from __future__ import annotations

import copy
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import scale_upem
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
TTF = DIST / "ttf"
TARGET_UPEM = 1024


def log(msg: str) -> None:
    print(msg, flush=True)


def strip_hints(font: TTFont) -> None:
    from fontTools.ttLib.tables import ttProgram

    n = 0
    if "glyf" in font:
        for name in font["glyf"].keys():
            g = font["glyf"][name]
            if getattr(g, "program", None) is not None:
                g.program = ttProgram.Program()
                g.program.fromBytecode(b"")
                n += 1
    for tag in ("fpgm", "prep", "cvt ", "hdmx", "LTSH", "VDMX"):
        if tag in font:
            del font[tag]
    log(f"      stripped hints from {n} glyphs")


def prepare(path: Path) -> TTFont:
    font = TTFont(path)
    upm = font["head"].unitsPerEm
    if upm != TARGET_UPEM:
        log(f"    scaling {path.name} {upm} -> {TARGET_UPEM}")
        scale_upem(font, TARGET_UPEM)
        strip_hints(font)
    return font


def collect_glyphs(font: TTFont, name: str, out: list[str], seen: set[str]) -> None:
    if name in seen:
        return
    seen.add(name)
    out.append(name)
    if "glyf" not in font:
        return
    g = font["glyf"][name]
    if g.isComposite():
        for comp in g.components:
            collect_glyphs(font, comp.glyphName, out, seen)


def merge_into(
    base: TTFont,
    extra: TTFont,
    skip_cps: set[int] | None = None,
    all_glyphs: bool = False,
) -> dict:
    skip_cps = skip_cps or set()
    base_cmap_names = set(base.getBestCmap())
    extra_cmap = extra.getBestCmap()

    base_glyf, extra_glyf = base["glyf"], extra["glyf"]
    base_hmtx, extra_hmtx = base["hmtx"], extra["hmtx"]

    order = list(base.getGlyphOrder())
    existing = set(order)
    added: list[str] = []
    added_cps: list[int] = []

    def copy_one(name: str) -> None:
        if name in existing:
            return
        base_glyf[name] = copy.deepcopy(extra_glyf[name])
        if name in extra_hmtx.metrics:
            base_hmtx[name] = extra_hmtx[name]
        else:
            base_hmtx[name] = (extra["head"].unitsPerEm // 2, 0)
        existing.add(name)
        order.append(name)
        added.append(name)

    def copy_with_components(name: str) -> None:
        if name in existing:
            return
        g = extra_glyf[name]
        if g.isComposite():
            for comp in g.components:
                copy_with_components(comp.glyphName)
        copy_one(name)

    for cp, gname in sorted(extra_cmap.items()):
        if cp in skip_cps or cp in base_cmap_names:
            continue
        copy_with_components(gname)
        added_cps.append(cp)

    if all_glyphs:
        for gname in extra.getGlyphOrder():
            copy_with_components(gname)

    base.setGlyphOrder(order)
    base["maxp"].numGlyphs = len(order)

    has_fmt12 = any(t.format == 12 for t in base["cmap"].tables)
    if not has_fmt12:
        st = CmapSubtable.newSubtable(12)
        st.platformID, st.platEncID, st.language, st.format = 3, 10, 0, 12
        st.cmap = {
            cp: g
            for t in base["cmap"].tables
            if t.isUnicode()
            for cp, g in t.cmap.items()
        }
        base["cmap"].tables.append(st)
        log(f"    added cmap format 12 subtable ({len(st.cmap)} existing cps)")

    for table in base["cmap"].tables:
        if not table.isUnicode():
            continue
        fmt = table.format
        for cp in added_cps:
            if fmt in (0, 4, 6) and cp > 0xFFFF:
                continue
            table.cmap[cp] = extra_cmap[cp]

    return {"glyphs": len(added), "cps": len(added_cps)}


def merge_colr(base: TTFont, extra: TTFont, reserved: set[str] | None = None) -> bool:
    if "COLR" not in extra or "CPAL" not in extra:
        return False
    if "COLR" in base:
        log("    base already has COLR, skipping")
        return False

    colr = copy.deepcopy(extra["COLR"])
    base_names = reserved if reserved is not None else set(base.getGlyphOrder())
    table = colr.table
    if getattr(table, "BaseGlyphList", None) is not None:
        records = table.BaseGlyphList.BaseGlyphPaintRecord
        kept = [r for r in records if r.BaseGlyph not in base_names]
        dropped = len(records) - len(kept)
        table.BaseGlyphList.BaseGlyphPaintRecord = kept
        if dropped:
            log(f"    COLR: dropped {dropped} base glyphs colliding with the base font")

    base["COLR"] = colr
    base["CPAL"] = copy.deepcopy(extra["CPAL"])
    return True


def merge_gsub(base: TTFont, extra: TTFont) -> int:
    if "GSUB" not in extra or "GSUB" not in base:
        return 0
    bg, eg = base["GSUB"].table, extra["GSUB"].table
    if not eg.LookupList or not eg.LookupList.Lookup:
        return 0

    offset = len(bg.LookupList.Lookup)
    for lk in eg.LookupList.Lookup:
        bg.LookupList.Lookup.append(copy.deepcopy(lk))
    bg.LookupList.LookupCount = len(bg.LookupList.Lookup)

    tag_to_idx: dict[str, int] = {}
    for i, fr in enumerate(bg.FeatureList.FeatureRecord):
        tag_to_idx.setdefault(fr.FeatureTag, i)

    touched = 0
    for fr in eg.FeatureList.FeatureRecord:
        shifted = [i + offset for i in fr.Feature.LookupListIndex]
        if fr.FeatureTag in tag_to_idx:
            target = bg.FeatureList.FeatureRecord[tag_to_idx[fr.FeatureTag]].Feature
            target.LookupListIndex += shifted
            target.LookupCount = len(target.LookupListIndex)
            touched += len(shifted)
            continue
        new_fr = copy.deepcopy(fr)
        new_fr.Feature.LookupListIndex = shifted
        new_fr.Feature.LookupCount = len(shifted)
        new_fr.Feature.FeatureParams = None
        bg.FeatureList.FeatureRecord.append(new_fr)
        bg.FeatureList.FeatureCount = len(bg.FeatureList.FeatureRecord)
        for sr in bg.ScriptList.ScriptRecord:
            if sr.ScriptTag != "DFLT" or sr.Script.DefaultLangSys is None:
                continue
            ls = sr.Script.DefaultLangSys
            ls.FeatureIndex.append(len(bg.FeatureList.FeatureRecord) - 1)
            ls.FeatureCount = len(ls.FeatureIndex)
        touched += len(shifted)
    return touched


def fix_post(font: TTFont) -> None:
    post = font["post"]
    post.formatType = 2.0
    post.extraNames = []
    post.mapping = {}
    post.glyphOrder = font.getGlyphOrder()


def save(font: TTFont, out: Path) -> None:
    fix_post(font)
    for t in [t for t in ("DSIG", "FFTM") if t in font]:
        del font[t]
    font.save(out)
    log(
        f"  -> dist/ttf/{out.name}  ({out.stat().st_size / 1048576:.2f} MB, "
        f"{font['maxp'].numGlyphs} glyphs, upm {font['head'].unitsPerEm})"
    )


def build_sans() -> None:
    from meta import apply, upstream_parts

    log("[combine:sans] Latin + CJK + Emoji  (local)")
    parts = upstream_parts()
    latin = prepare(TTF / "YumeSansLatin-Regular.ttf")
    cjk = prepare(TTF / "YumeSansCJK-Regular.ttf")
    emoji = prepare(TTF / "YumeSansEmoji-Regular.ttf")

    st1 = merge_into(latin, cjk)
    log(f"    + cjk: {st1['glyphs']} glyphs / {st1['cps']} cps")
    reserved = set(latin.getGlyphOrder())
    st2 = merge_into(latin, emoji, all_glyphs=True)
    log(f"    + emoji: {st2['glyphs']} glyphs / {st2['cps']} cps")
    log(f"    + COLR: {merge_colr(latin, emoji, reserved)}")
    log(f"    + GSUB features: {merge_gsub(latin, emoji)}")

    apply(
        latin,
        family="YumeSans",
        ps_name="YumeSans-Regular",
        parts=[parts["ubuntu"], parts["chill"], parts["noto"]],
    )
    save(latin, TTF / "YumeSans-Regular.ttf")


def build_mono_all() -> None:
    from meta import apply, upstream_parts

    log("[combine:mono-all] Mono + Emoji")
    parts = upstream_parts()
    mono = prepare(TTF / "YumeSansMono-Regular.ttf")
    emoji = prepare(TTF / "YumeSansEmoji-Regular.ttf")

    reserved = set(mono.getGlyphOrder())
    st = merge_into(mono, emoji, all_glyphs=True)
    log(f"    + emoji: {st['glyphs']} glyphs / {st['cps']} cps")
    log(f"    + COLR: {merge_colr(mono, emoji, reserved)}")
    log(f"    + GSUB features: {merge_gsub(mono, emoji)}")

    apply(
        mono,
        family="YumeSans Mono ALL",
        ps_name="YumeSansMonoALL-Regular",
        parts=[parts["fusion"], parts["noto"]],
    )
    save(mono, TTF / "YumeSansMonoALL-Regular.ttf")


def main() -> None:
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("sans", "all"):
        build_sans()
    if what in ("mono-all", "all"):
        build_mono_all()


if __name__ == "__main__":
    main()
