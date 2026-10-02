"""The Indonesian catalog covers the code, compiles, and every translation formats safely."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, have, load_mo  # noqa: E402
import re, string

if not have("babel"):
    print("SKIP  translation catalog tests (pip install -r tests/requirements.txt)")
    print(); print("FAILURES: none"); sys.exit(0)
from babel.messages.pofile import read_po
import _strings

ROOT = REPO
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

PO = {lang: os.path.join(ROOT, "addon", "locale", lang, "LC_MESSAGES", "nvda.po") for lang in ("id", "en")}
cat = read_po(open(PO["id"], "rb"))
entries = {m.id: m.string for m in cat if m.id}

# Every string the code translates is in the catalog, and translated.
code_ids = {m.id for m in _strings.template() if m.id}
missing = sorted(code_ids - set(entries))
check(f"every translatable string in the code is in the catalog ({len(code_ids)} strings, missing {missing[:3]})", not missing)
untranslated = [i for i in code_ids if not entries.get(i) and not str(i).startswith("\n- ")]
check(f"all of them are translated, except the per-release changelog ({untranslated[:3]})", not untranslated)
check("no obsolete entries are kept", not cat.obsolete and set(entries) <= code_ids)
check("no entry is marked fuzzy (msgfmt would skip it)", not [m.id for m in cat if m.id and "fuzzy" in m.flags])

# It compiles, and gettext returns the translations.
try:
    t = load_mo(PO["id"]); compiled = True
except Exception as e:
    t, compiled = None, False; print("      ", e)
check("the catalog compiles", compiled)
check("gettext returns Indonesian", t.gettext("Show Lyrics") == "Tampilkan Lirik" and t.gettext("&Close") == "&Tutup")

# Formatting every translation with the arguments the original takes must work.
bad = []
for msgid, msgstr in entries.items():
    if not isinstance(msgid, str) or not msgstr:
        continue
    fields = [f for _, f, _, _ in string.Formatter().parse(msgid) if f is not None]
    if not fields:
        continue
    named = {f: "X" for f in fields if f}
    positional = ["X"] * sum(1 for f in fields if f == "")
    try:
        msgstr.format(*positional, **named)
    except Exception as e:
        bad.append((msgid, type(e).__name__))
check(f"every translation formats with the original's arguments ({bad[:3] or 'all do'})", not bad)

# Fixes made while reviewing the old translations.
for msgid, expected in (("Now following artist: {artist_name}.", "Sekarang mengikuti artis: {artist_name}."),
                        ("Copy Link\tAlt+L", "Salin Tautan\tAlt+L"), ("Add to Queue\tAlt+Q", "Tambahkan ke Antrean\tAlt+Q"),
                        ("Follow/Unfollow Artist\tAlt+F", "Ikuti/Berhenti Mengikuti Artis\tAlt+F"), ("Repeat: One Track", "Ulangi: Satu Trek"),
                        ("Show:", "Tampilkan:")):
    check(f"fixed: {msgid!r} -> {expected!r}", entries.get(msgid) == expected)
check("menu shortcuts after a tab are never translated",
      all(m.split("\t")[1] == s.split("\t")[1] for m, s in entries.items() if isinstance(m, str) and "\t" in m and s))

# No two buttons in the lyrics window share an Alt letter in Indonesian.
letters = [re.search(r"&(\w)", entries[k]).group(1).upper() for k in
           ("&Close", "Copy &Lyrics", "Copy with &Timestamps", "&Jump to Current")]
check(f"lyrics window mnemonics are distinct in Indonesian ({letters})", len(set(letters)) == len(letters))

# The English catalog is a refreshed template: same entries, nothing translated.
en = read_po(open(PO["en"], "rb"))
check("the English catalog lists the same strings, untranslated",
      {m.id for m in en if m.id} == code_ids and not [m for m in en if m.id and m.string])

# Translated text must not contain raw English inserted at runtime.
src = open(os.path.join(ROOT, "addon", "globalPlugins", "accesifyPlay", "ui", "base_dialog.py"), encoding="utf-8").read()
check("the queue refusal no longer inserts the English item type", "{item_type}" not in src)

for lang, path in PO.items():
    raw = open(path, "rb").read()
    # CRLF in a Windows checkout, LF elsewhere (.gitattributes text=auto); never a mix.
    check(f"{lang}: consistent line endings and UTF-8", raw.count(b"\r\n") in (0, raw.count(b"\n")) and raw.decode("utf-8"))

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)
