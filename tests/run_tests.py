"""Run every test script in this folder and report the results.

Each test_*.py is a standalone script that prints PASS/FAIL/SKIP lines and
exits non-zero on failure. They stub out NVDA and wx, so no NVDA is needed.

    pip install -r tests/requirements.txt
    python tests/run_tests.py            # all tests
    python tests/run_tests.py lyrics     # only test files whose name contains "lyrics"
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

#: Tests that must run without site-packages, as NVDA's own Python does.
ISOLATED = {"test_libclean.py"}


def main(filters):
	tests = sorted(f for f in os.listdir(HERE) if f.startswith("test_") and f.endswith(".py"))
	if filters:
		tests = [t for t in tests if any(f in t for f in filters)]
	failed, passed, skipped = [], 0, 0
	for name in tests:
		flags = ["-I", "-S"] if name in ISOLATED else []
		proc = subprocess.run(
			[sys.executable, *flags, os.path.join(HERE, name)],
			capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=HERE,
		)
		lines = proc.stdout.splitlines()
		passed += sum(line.startswith("PASS") for line in lines)
		skipped += sum(line.startswith("SKIP") for line in lines)
		fails = [line for line in lines if line.startswith("FAIL ")]
		ok = proc.returncode == 0 and not fails
		print(f"{'ok  ' if ok else 'FAIL'}  {name}")
		if not ok:
			failed.append(name)
			for line in fails[:10]:
				print("      " + line)
			if proc.returncode and not fails:
				print("      " + "\n      ".join((proc.stderr or proc.stdout).strip().splitlines()[-8:]))
	print(f"\n{len(tests)} files, {passed} checks passed, {skipped} skipped, {len(failed)} files failed")
	return 1 if failed else 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
