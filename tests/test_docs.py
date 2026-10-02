"""The user guides match the code and build into a package NVDA can open."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import os, re, sys

ROOT = REPO
DOC = os.path.join(ROOT, "addon", "doc")
PKG = os.path.join(ROOT, "addon", "globalPlugins", "accesifyPlay")
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

LANGS = ("en", "id")
pages = {lang: sorted(f for f in os.listdir(os.path.join(DOC, lang)) if f.endswith(".md")) for lang in LANGS}
check(f"both languages have the same pages ({pages['en']})", pages["en"] == pages["id"])
check("each language has readme.md, in lower case, for docFileName = readme.html",
      all("readme.md" in pages[l] for l in LANGS))
check("no generated HTML is kept in the source tree",
      not [f for l in LANGS for f in os.listdir(os.path.join(DOC, l)) if f.endswith(".html")])
check("obsolete pages are gone", not {"authentication.md", "features.md"} & set(pages["en"]))

text = {(l, f): open(os.path.join(DOC, l, f), encoding="utf-8").read() for l in LANGS for f in pages[l]}

# Links between pages resolve.
broken = [(l, f, t) for (l, f), s in text.items() for t in re.findall(r"\]\(([^)#:]+\.html)\)", s)
          if not os.path.exists(os.path.join(DOC, l, t[:-5] + ".md"))]
check(f"every link between pages resolves ({broken or 'none broken'})", not broken)
orphans = [f for f in pages["en"] if f != "readme.md"
           and not any(f[:-3] + ".html" in s for (l, g), s in text.items() if l == "en")]
check(f"every page is linked from another ({orphans or 'none orphaned'})", not orphans)

# Nothing describes setups that no longer exist.
STALE = ["Client ID is correct", "Developer Dashboard", "Callback Port", "8888", "8539", "NVDA+Shift+Alt",
         "NVDA+Alt+Shift", "NVDA+G`", "Migrate Old Credentials", "Check for Updates", "Update Channel",
         "related artists", "Related Artists", "auto-update"]
for (l, f), s in text.items():
    hits = [w for w in STALE if w in s]
    if hits: check(f"{l}/{f}: no stale content ({hits})", False)
check("no page mentions removed setup steps or old shortcuts", not [1 for (l, f), s in text.items() for w in STALE if w in s])

# The key tables match the default command layer.
spec = re.findall(r'\("(\w+)", "kb:([^"]+)",', open(os.path.join(PKG, "layer_config.py"), encoding="utf-8").read())
keys = {k.upper() if len(k) == 1 else k.upper() for _s, k in spec} | {"F1", "F2", "ESCAPE"}
for l in LANGS:
    doc_keys = {k.upper() for k in re.findall(r"^\| `([^`]+)` \|", text[(l, "keybindings.md")], re.M)}
    check(f"{l}/keybindings.md lists exactly the layer's keys (missing {sorted(keys - doc_keys)}, extra {sorted(doc_keys - keys)})",
          doc_keys == keys)
    stays = set(re.findall(r"^\| `([^`]+)` \|[^|]*\((?:stays open|tetap terbuka)\)", text[(l, "keybindings.md")], re.M))
    keep_open = {k for _s, k, flag in re.findall(r'^		\("(\w+)", "kb:([^"]+)", .*, (True|False)\),\s*$',
                 open(os.path.join(PKG, "layer_config.py"), encoding="utf-8").read(), re.M) if flag == "True"}
    check(f"{l}/keybindings.md marks exactly the commands that keep the layer open ({sorted(stays)})", {k.upper() for k in stays} == {k.upper() for k in keep_open})

readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
root_keys = {k.upper() for k in re.findall(r"\| `([^`]+)` \|", readme)}
root_keys |= {k.upper() for pair in re.findall(r"\| `([^`]+)` / `([^`]+)` \|", readme) for k in pair}
check(f"README.md's key table covers the layer (missing {sorted(keys - {'ESCAPE'} - root_keys)})",
      not (keys - {"ESCAPE"} - root_keys))
check("README.md has no stale shortcut table or broken lint badge",
      "NVDA+Shift+Alt" not in readme and "lint.yml" not in readme and "2024.4" not in readme)

# Settings named in the guide are the ones in the panel.
settings = open(os.path.join(PKG, "dialogs", "settings.py"), encoding="utf-8").read()
for label in ("Search Results Limit (1 to 50)", "Seek Duration (seconds, 1 to 60)", "Volume Step (1 to 100)",
              "Keep Alive Interval (seconds, 0 = Off, Min = 5)", "Validate Credentials", "Clear Credentials", "Donate"):
    check(f"settings label '{label}' exists and is documented in both languages",
          label in settings and all(label in text[(l, "configuration.md")] for l in LANGS))

build = open(os.path.join(ROOT, "buildVars.py"), encoding="utf-8").read()
check("tables are rendered (markdown tables extension enabled)", '"markdown.extensions.tables"' in build)
check("minimum NVDA version in the guide matches buildVars",
      re.search(r'addon_minimumNVDAVersion="([^"]+)"', build).group(1) == "2025.1"
      and all("NVDA 2025.1" in text[(l, "readme.md")] for l in LANGS))
sc = open(os.path.join(ROOT, "sconstruct"), encoding="utf-8").read()
check("the build no longer copies the repository readme over the guide", 'Path("readme.md")' not in sc)

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)
