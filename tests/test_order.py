"""Guard the import ordering that broke 1.10.0.

GlobalPlugin.__init__ died with KeyError: 'isAutomaticallyCheckForUpdates'
because an add-on module was imported before config.conf.spec["spotify"] was
registered. Importing one can evaluate _() at class-body level, which reads
that section; reading it first materialises it without the spec's defaults.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import re, sys

PATH = os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay", "__init__.py")
lines = open(PATH, encoding="utf-8").read().split("\n")

FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

spec_line = next((i for i, l in enumerate(lines)
                  if 'config.conf.spec["spotify"]' in l and not l.lstrip().startswith("#")), None)
check("config spec is registered", spec_line is not None)

# Any import of an add-on module: `from . import ...` / `from .x import ...`
rel_imports = [(i, l) for i, l in enumerate(lines)
               if re.match(r"\s*from \.", l) and not l.lstrip().startswith("#")]
check("add-on modules are imported", bool(rel_imports))

first_rel, first_src = rel_imports[0]
check(f"spec precedes every add-on import (spec line {spec_line + 1}, first import line {first_rel + 1}: {first_src.strip()[:40]})",
      spec_line < first_rel)

# thread_manager is imported at the very top and must stay config-free.
tm = open(os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay", "core", "thread_manager.py"),
          encoding="utf-8").read()
check("thread_manager does not read config", "config.conf" not in tm)

# Every key __init__ reads must exist in the spec it registers.
src = "\n".join(lines)
spec_block = re.search(r"confspec = \{(.*?)\n\}", src, re.S).group(1)
declared = set(re.findall(r'"(\w+)":', spec_block))
used = set(re.findall(r'config\.conf\["spotify"\]\["(\w+)"\]', src))
missing = used - declared
check(f"every config key __init__ uses is declared (missing: {sorted(missing) or 'none'})", not missing)

print()
print("FAILURES:", FAILS if FAILS else "none")
sys.exit(1 if FAILS else 0)
