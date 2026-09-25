"""Extract the game's own UI art from the client for the dashboard's Warcraft skin.

The dashboard frames its panels, buttons and hover cards with the same textures the
game uses (dialog borders, the red panel buttons, tooltip borders, class icons). These
are Blizzard's art, read from the client already installed on this machine, and are
git-ignored like the map art. Without them the page falls back to a CSS look.

Writes ui/<stem>.png for every texture below, plus manifest.json listing the
stems that were written. The page only switches to the client art when the manifest
loads.

Standard library only (tools/wowart.py reads the archives and textures).
"""
import argparse
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wowart  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_OUT = os.path.join(ROOT, "ui")
MANIFEST_VERSION = 1

SEP = chr(92)


def _p(*parts):
    return SEP.join(("Interface",) + parts)


# stem -> path inside the client MPQs. Stems are what the page asks for.
FRAMES = {
    "dialog-border": _p("DialogFrame", "UI-DialogBox-Border.blp"),
    "dialog-gold-border": _p("DialogFrame", "UI-DialogBox-Gold-Border.blp"),
    "dialog-background": _p("DialogFrame", "UI-DialogBox-Background.blp"),
    "dialog-header": _p("DialogFrame", "UI-DialogBox-Header.blp"),
    "panel-button-up": _p("Buttons", "UI-Panel-Button-Up.blp"),
    "panel-button-down": _p("Buttons", "UI-Panel-Button-Down.blp"),
    "panel-button-highlight": _p("Buttons", "UI-Panel-Button-Highlight.blp"),
    "panel-button-disabled": _p("Buttons", "UI-Panel-Button-Disabled.blp"),
    "tooltip-border": _p("Tooltips", "UI-Tooltip-Border.blp"),
    "tooltip-background": _p("Tooltips", "UI-Tooltip-Background.blp"),
    "input-border": _p("Common", "Common-Input-Border.blp"),
    "status-bar": _p("TargetingFrame", "UI-StatusBar.blp"),
    "parchment": _p("AchievementFrame", "UI-Achievement-Parchment-Horizontal.blp"),
    "logo": _p("Glues", "Common", "Glues-WoW-WotLKLogo.blp"),
    "backdrop": _p("Glues", "LoadingScreens", "LoadScreenNorthrendWide.blp"),
}

# The panel buttons only use the top-left 80x22 of their 128x32 texture (the rest is
# padding to a power of two); crop so CSS can stretch the button itself.
CROPS = {
    "panel-button-up": (0, 0, 80, 22),
    "panel-button-down": (0, 0, 80, 22),
    "panel-button-highlight": (0, 0, 80, 22),
    "panel-button-disabled": (0, 0, 80, 22),
}

ICONS = {
    "icon-world": "INV_Misc_Map_01",
    "icon-bots": "Achievement_Character_Human_Male",
    "icon-stats": "INV_Misc_Book_09",
    "icon-chat": "INV_Letter_15",
    "icon-settings": "Trade_Engineering",
}


def class_tokens(dbc_dir):
    """{class id: token} from the server's ChrClasses.dbc (3.3.5 layout, token in field 55).

    The icon follows the token, not the display name: on Conquest of Azeroth class 14 shows
    "Felsworn" and its icon is ClassIcon_DEMONHUNTER."""
    raw = open(os.path.join(dbc_dir, "ChrClasses.dbc"), "rb").read()
    magic, records, fields, size, _ = struct.unpack("<4siiii", raw[:20])
    if magic != b"WDBC" or fields < 56:
        raise SystemExit("ChrClasses.dbc: unexpected layout")
    body, block = raw[20:20 + records * size], raw[20 + records * size:]
    out = {}
    for i in range(records):
        row = struct.unpack_from("<%dI" % fields, body, i * size)
        token = block[row[55]:block.index(bytes(1), row[55])].decode("ascii", "replace")
        if re.match(r"^[A-Z_]+$", token):
            out[row[0]] = token
    return out


def textures(dbc_dir):
    out = dict(FRAMES)
    for stem, icon in ICONS.items():
        out[stem] = _p("Icons", icon + ".blp")
    for class_id, token in class_tokens(dbc_dir).items():
        out["class-%d" % class_id] = _p("Icons", "ClassIcon_%s.blp" % token)
    return out


# 9-slice frames built from WoW edge strips, so CSS border-image can use them.
# output stem -> source texture stem.
FRAME_SHEETS = {
    "frame-dialog": "dialog-border",
    "frame-gold": "dialog-gold-border",
    "frame-tooltip": "tooltip-border",
}


def nine_slice(strip):
    """Turn a WoW edge strip into a 3x3 sheet CSS border-image can slice.

    The strip is 8 square pieces in a row: left, right, top and bottom edges (the
    top and bottom stored sideways, as vertical strips), then the top-left,
    top-right, bottom-left and bottom-right corners. The middle is left empty; the
    panel background is drawn separately."""
    size = strip.height
    piece = [strip.crop(i * size, 0, i * size + size, size) for i in range(8)]
    # A clockwise quarter turn brings the stored strip's left side to the top (for
    # the top edge) and its right side to the bottom (for the bottom edge).
    top = piece[2].turned_clockwise()
    bottom = piece[3].turned_clockwise()
    sheet = wowart.Image(size * 3, size * 3)
    for image, col, row in ((piece[4], 0, 0), (top, 1, 0), (piece[5], 2, 0),
                            (piece[0], 0, 1), (piece[1], 2, 1),
                            (piece[6], 0, 2), (bottom, 1, 2), (piece[7], 2, 2)):
        sheet.paste(image, col * size, row * size)
    return sheet


def write_manifest(out_dir, stems):
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8", newline="") as handle:
        json.dump({"version": MANIFEST_VERSION, "files": list(stems)}, handle)


def check(out_dir, dbc_dir):
    wanted = list(textures(dbc_dir)) + list(FRAME_SHEETS)
    missing = [stem for stem in wanted
               if not os.path.exists(os.path.join(out_dir, "%s.png" % stem))]
    if not os.path.exists(os.path.join(out_dir, "manifest.json")):
        missing.append("manifest.json")
    if missing:
        print("MISSING UI art: %s" % ", ".join(missing), file=sys.stderr)
        print("Run: python tools/gen_uiart.py --client <client> --dbc <dbc>", file=sys.stderr)
        return 1
    print("OK: all %d UI textures present in %s" % (len(wanted), out_dir))
    return 0


def run(client, dbc_dir, out_dir, say=print):
    """Write every texture and the manifest. Returns the stems that could not be read."""
    os.makedirs(out_dir, exist_ok=True)
    written, failed, images = [], [], {}
    for stem, path in sorted(textures(dbc_dir).items()):
        image = client.image(path)
        if image is None:
            failed.append(stem)
            say("  %-24s MISSING %s" % (stem, path))
            continue
        if stem in CROPS:
            image = image.crop(*CROPS[stem])
        image.save_png(os.path.join(out_dir, "%s.png" % stem))
        images[stem] = image
        written.append(stem)
    for stem, source in FRAME_SHEETS.items():
        if source not in images:
            failed.append(stem)
            continue
        nine_slice(images[source]).save_png(os.path.join(out_dir, "%s.png" % stem))
        written.append(stem)
    write_manifest(out_dir, written)
    say("Wrote %d UI textures to %s" % (len(written), out_dir))
    return failed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True,
                        help="the game client folder, the one holding Data/")
    parser.add_argument("--dbc", required=True,
                        help="the server's dbc folder (ChrClasses.dbc names the class icons)")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true",
                        help="write nothing; report whether every texture is present")
    args = parser.parse_args(argv)

    if args.check:
        return check(args.out, args.dbc)
    client = wowart.Client(args.client)
    if not client.archives:
        print("No readable MPQ archives in %s" % args.client, file=sys.stderr)
        return 1
    return 1 if run(client, args.dbc, args.out) else 0


if __name__ == "__main__":
    sys.exit(main())
