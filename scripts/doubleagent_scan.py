#!/usr/bin/env python3
"""DoubleAgent.scan: find content in agent instruction files that humans can't see
but AI agents can read.

Usage:
    python scripts/doubleagent_scan.py              # scan known agent files under the current directory
    python scripts/doubleagent_scan.py DIR [...]    # scan known agent files under the given directories
    python scripts/doubleagent_scan.py FILE [...]   # scan the given files (files and directories can mix)
    python scripts/doubleagent_scan.py --all DIR    # scan every Markdown and text file under DIR
    python scripts/doubleagent_scan.py --ascii ...  # also flag every non-ASCII character

Exit code: 0 = clean, 1 = findings, 2 = usage or read error.
Standard library only, so it can run anywhere without installing anything.
"""

import argparse
import os
import re
import sys
import unicodedata

AGENT_FILE_NAMES = {
    "agents.md", "agent.md", "claude.md", "claude.local.md", "gemini.md",
    ".cursorrules", ".windsurfrules", ".clinerules", "copilot-instructions.md",
    "skill.md", "conventions.md",
}
AGENT_FILE_SUFFIXES = (".mdc", ".instructions.md", ".prompt.md")
TEXT_SUFFIXES = (".md", ".markdown", ".mdc", ".mdx", ".txt", ".rst")  # for --all
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}

LONG_LINE = 1000  # characters; text past this is often off-screen in editors and diff views

BIDI = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A)) | {0x200E, 0x200F, 0x061C}
ZERO_WIDTH = {0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x180E}


def is_tag(cp):
    return 0xE0000 <= cp <= 0xE007F


def variation_selector_byte(cp):
    """Return the byte value a variation selector can encode, or None."""
    if 0xFE00 <= cp <= 0xFE0F:
        return cp - 0xFE00
    if 0xE0100 <= cp <= 0xE01EF:
        return cp - 0xE0100 + 16
    return None


def show(text, limit=160):
    """Make hidden characters visible for the report."""
    out = []
    for ch in text:
        cp = ord(ch)
        if ch == "\n":
            out.append("\\n")
        elif 32 <= cp < 127:
            out.append(ch)
        else:
            out.append(f"\\u{cp:04x}" if cp <= 0xFFFF else f"\\U{cp:08x}")
    s = "".join(out)
    return s if len(s) <= limit else s[:limit] + "..."


class Report:
    def __init__(self, path):
        self.path = path
        self.items = []

    def add(self, line, col, level, msg):
        self.items.append((line, col, level, msg))

    def print(self):
        for line, col, level, msg in sorted(self.items):
            print(f"{self.path}:{line}:{col}: {level}: {msg}")


def scan_unicode(text, rep, ascii_only):
    lines = text.split("\n")
    for ln, line in enumerate(lines, 1):
        i = 0
        while i < len(line):
            ch = line[i]
            cp = ord(ch)
            col = i + 1

            if is_tag(cp):
                j = i
                while j < len(line) and is_tag(ord(line[j])):
                    j += 1
                decoded = "".join(
                    chr(ord(c) - 0xE0000) if 0x20 <= ord(c) - 0xE0000 < 0x7F else "?"
                    for c in line[i:j]
                )
                rep.add(ln, col, "HIGH",
                        f"{j - i} invisible Unicode tag characters, decoded text: {decoded!r}")
                i = j
                continue

            vs = variation_selector_byte(cp)
            if vs is not None:
                j = i
                while j < len(line) and variation_selector_byte(ord(line[j])) is not None:
                    j += 1
                n = j - i
                # A single U+FE0E/U+FE0F after an emoji is normal; anything else is not.
                if n == 1 and cp in (0xFE0E, 0xFE0F) and not ascii_only:
                    i = j
                    continue
                data = bytes(variation_selector_byte(ord(c)) for c in line[i:j])
                level = "HIGH" if n > 1 else "WARN"
                rep.add(ln, col, level,
                        f"{n} variation selector(s), can smuggle bytes; as UTF-8: "
                        f"{data.decode('utf-8', 'replace')!r}")
                i = j
                continue

            if cp in BIDI:
                pass  # reported once per line below
            elif cp in ZERO_WIDTH:
                if cp == 0xFEFF and ln == 1 and i == 0:
                    rep.add(ln, col, "WARN", "byte order mark at start of file")
                else:
                    j = i
                    while j < len(line) and ord(line[j]) in ZERO_WIDTH:
                        j += 1
                    if j - i == 1:
                        rep.add(ln, col, "HIGH",
                                f"zero-width character U+{cp:04X} ({unicodedata.name(ch, '?')})")
                    else:
                        kinds = ", ".join(sorted({f"U+{ord(c):04X}" for c in line[i:j]}))
                        rep.add(ln, col, "HIGH",
                                f"{j - i} zero-width characters in a row ({kinds}), "
                                f"may encode a hidden message as bits")
                    i = j
                    continue
            elif unicodedata.category(ch) == "Cc" and ch not in "\t\r":
                if cp == 0x1B:
                    rep.add(ln, col, "HIGH", "ESC control character (U+001B), starts a terminal "
                            "escape code that can hide text in a terminal")
                else:
                    rep.add(ln, col, "HIGH", f"control character U+{cp:04X}")
            elif unicodedata.category(ch) == "Cf":
                rep.add(ln, col, "HIGH",
                        f"invisible format character U+{cp:04X} ({unicodedata.name(ch, '?')})")
            elif unicodedata.category(ch) in ("Co", "Cn"):
                rep.add(ln, col, "WARN", f"private-use or unassigned character U+{cp:04X}")
            elif unicodedata.category(ch) == "Zs" and ch != " ":
                rep.add(ln, col, "WARN",
                        f"unusual space U+{cp:04X} ({unicodedata.name(ch, '?')})")
            elif ascii_only and cp > 0x7E:
                rep.add(ln, col, "WARN",
                        f"non-ASCII character U+{cp:04X} ({unicodedata.name(ch, '?')}), "
                        f"could be a look-alike letter")
            i += 1

        bidi = [k for k, c in enumerate(line) if ord(c) in BIDI]
        if bidi:
            kinds = ", ".join(sorted({f"U+{ord(line[k]):04X}" for k in bidi}))
            rep.add(ln, bidi[0] + 1, "HIGH",
                    f"{len(bidi)} bidirectional control character(s) ({kinds}), text may "
                    f"display in a different order than it reads: {show(line)}")
        if len(line) > LONG_LINE:
            rep.add(ln, LONG_LINE, "WARN",
                    f"very long line ({len(line)} chars), text at the end may be off-screen")
        m = re.search(r"\S([ \t]{60,})\S", line)
        if m:
            rep.add(ln, m.start(1) + 1, "WARN",
                    f"{len(m.group(1))} whitespace characters before more text, "
                    f"may push content out of view")


HTML_TAG = re.compile(r"<[a-z][\w-]*((?:\s+[^\s=>/]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+))?)*)",
                      re.IGNORECASE)
HTML_ATTR = re.compile(r"([^\s=>/]+)(?:\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+))?")
HIDING_CSS = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(?![.\d]*[1-9])|"
    r"opacity\s*:\s*0(?![.\d]*[1-9])|(?:max-)?(?:height|width)\s*:\s*0(?![.\d]*[1-9])|"
    r"position\s*:\s*absolute",
    re.IGNORECASE,
)


def find_hidden_html(line):
    """Column of the first HTML tag hidden by an attribute or by CSS, or None."""
    for tag in HTML_TAG.finditer(line):
        for attr in HTML_ATTR.finditer(tag.group(1)):
            name = attr.group(1).lower()
            value = (attr.group(2) or "").strip("\"'")
            if name in ("hidden", "aria-hidden") or (name == "style" and HIDING_CSS.search(value)):
                return tag.start()
    return None
# Any text color is suspicious: it can match the page background (white on white, or
# dark on dark). An instruction file has no legitimate reason to color its text.
COLORED_HTML = re.compile(r"<[a-z][^>]*\b(color\s*[:=]|bgcolor\s*=)", re.IGNORECASE)
# Math (rendered on GitHub with $...$ and $$...$$) can color text or draw it invisibly.
MATH_HIDING = re.compile(r"\\(color|textcolor|colorbox|phantom|hphantom|vphantom)\b")
LINK_TITLE = re.compile(r"\]\(\s*\S*\s+(\"[^\"]*\"|'[^']*'|\([^)]*\))\s*\)")
DEF_TITLE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*\S+\s+(\"[^\"]*\"|'[^']*'|\([^)]*\))\s*$")
IMAGE_ALT = re.compile(r"!\[([^\]]+)\]")
LINK_DEF_COMMENT = re.compile(r"^\s{0,3}\[[^\]]*\]:\s*(#|<>)")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
INLINE_CODE = re.compile(r"(`+)[^`\n]*?\1")


def scan_markup(text, rep):
    """Markdown/HTML constructs that are hidden when the file is rendered.

    Skips fenced code blocks, where such text is shown literally.
    """
    lines = text.split("\n")
    fence = None
    in_comment_since = None
    comment_buf = []

    for ln, line in enumerate(lines, 1):
        m = FENCE.match(line)
        if in_comment_since is None and m:
            marker = m.group(1)
            if fence is None:
                fence = marker[0] * len(marker)
            elif marker.startswith(fence):
                fence = None
            continue
        if fence is not None:
            continue

        # Inline `code` is shown literally, so blank it out (keeping column numbers).
        line = INLINE_CODE.sub(lambda c: " " * len(c.group(0)), line)

        pos = 0
        while True:
            if in_comment_since is None:
                start = line.find("<!--", pos)
                if start < 0:
                    break
                in_comment_since = (ln, start + 1)
                comment_buf = []
                pos = start + 4
            end = line.find("-->", pos)
            if end < 0:
                comment_buf.append(line[pos:])
                break
            comment_buf.append(line[pos:end])
            body = "\n".join(comment_buf).strip()
            cl, cc = in_comment_since
            rep.add(cl, cc, "HIGH",
                    f"HTML comment, invisible when rendered: {show(body) or '(empty)'}")
            in_comment_since = None
            pos = end + 3

        if LINK_DEF_COMMENT.match(line):
            rep.add(ln, 1, "HIGH",
                    f"markdown link-definition comment, invisible when rendered: {show(line)}")
        hidden_col = find_hidden_html(line)
        if hidden_col is not None:
            rep.add(ln, hidden_col + 1, "HIGH",
                    f"HTML element styled to be hidden: {show(line)}")
        cm = COLORED_HTML.search(line)
        if cm:
            rep.add(ln, cm.start() + 1, "HIGH",
                    f"HTML sets a text color, may match the background: {show(line)}")
        mm = MATH_HIDING.search(line)
        if mm:
            rep.add(ln, mm.start() + 1, "HIGH",
                    f"math \\{mm.group(1)} can color text or make it invisible: {show(line)}")
        if re.search(r"<details\b", line, re.IGNORECASE):
            rep.add(ln, 1, "WARN", "<details> block, collapsed (not visible) by default")
        titles = list(LINK_TITLE.finditer(line))
        if not LINK_DEF_COMMENT.match(line) and DEF_TITLE.match(line):
            titles.append(DEF_TITLE.match(line))
        for tm in titles:
            rep.add(ln, tm.start(1) + 1, "WARN",
                    f"link title, only shown on mouse hover: {show(tm.group(1))}")
        for am in IMAGE_ALT.finditer(line):
            rep.add(ln, am.start() + 1, "WARN",
                    f"image alt text, not shown when the image loads: {show(am.group(1))}")

    if in_comment_since is not None:
        cl, cc = in_comment_since
        rep.add(cl, cc, "HIGH", "unclosed HTML comment hides the rest of the file")


def find_agent_files(root, include_all=False):
    """Agent instruction files under root (with include_all: every Markdown/text file)."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            low = name.lower()
            if (low in AGENT_FILE_NAMES or low.endswith(AGENT_FILE_SUFFIXES)
                    or (include_all and low.endswith(TEXT_SUFFIXES))):
                found.append(os.path.join(dirpath, name))
    return found


def collect_targets(paths, include_all):
    """Expand directories into the files to scan. Returns (files, errors)."""
    files, errors = [], 0
    for path in paths:
        if os.path.isdir(path):
            matches = find_agent_files(path, include_all)
            if not matches:
                hint = "" if include_all else " (use --all to scan every Markdown and text file)"
                print(f"{path}: no agent instruction files found{hint}")
            files.extend(matches)
        elif os.path.isfile(path):
            files.append(path)
        else:
            print(f"{path}: ERROR: no such file or directory", file=sys.stderr)
            errors += 1
    unique = list(dict.fromkeys(os.path.normpath(f) for f in files))
    return unique, errors


def scan_file(path, ascii_only):
    rep = Report(path)
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        print(f"{path}: ERROR: cannot read: {e}", file=sys.stderr)
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        rep.add(1, 1, "WARN", f"not valid UTF-8 ({e}); scanning with replacement characters")
        text = raw.decode("utf-8", "replace")
    text = text.replace("\r\n", "\n")
    scan_unicode(text, rep, ascii_only)
    scan_markup(text, rep)
    return rep


def main():
    ap = argparse.ArgumentParser(
        prog="doubleagent_scan.py",
        description="DoubleAgent.scan: find content in agent instruction files that "
                    "humans can't see but AI agents can read.")
    ap.add_argument("paths", nargs="*", metavar="PATH",
                    help="files or directories to scan (default: the current directory). "
                         "Directories are searched recursively for agent instruction files.")
    ap.add_argument("--all", action="store_true",
                    help="in directories, scan every Markdown and text file, not only agent files")
    ap.add_argument("--ascii", action="store_true",
                    help="flag every non-ASCII character (recommended for AGENTS.md)")
    args = ap.parse_args()

    paths = args.paths or ["."]
    files, errors = collect_targets(paths, args.all)
    if not files:
        if not errors and not any(os.path.isdir(p) for p in paths):
            print("No files to scan.")
        return 2 if errors else 0

    found = 0
    for path in files:
        rep = scan_file(path, args.ascii)
        if rep is None:
            errors += 1
            continue
        if rep.items:
            rep.print()
            found += len(rep.items)
        else:
            print(f"{path}: OK")

    if found:
        print(f"\n{found} finding(s). Review them in a hex/escape view before trusting these files.")
        return 1
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
