#!/usr/bin/env python3
import os
import sys
import subprocess

cd = os.path.dirname(os.path.abspath(__file__))

# Root addon dan locale
addon_root = os.path.join(cd, "addon")
locale_path = os.path.join(addon_root, "locale")
pot_file_path = os.path.join(locale_path, "nvda.pot")

# Folder sumber kode yang mau discan
source_root = os.path.join(addon_root, "globalPlugins", "accesifyPlay")

babel_prefix = f'"{sys.executable}" -m babel.messages.frontend'
locale_domain = "nvda"


def collect_py_files(root):
    py_files = []
    for base, dirs, files in os.walk(root):
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(base, f))
    return py_files


def extract():
    # Kumpulkan semua file .py di dalam accesifyPlay
    files = collect_py_files(source_root)

    file_list = " ".join(f'"{f}"' for f in files)

    cmd = (
        f'{babel_prefix} extract {file_list} '
        f'-o "{pot_file_path}" '
        f'--keywords=_ -c translators: --project=AccessifyPlay'
    )

    code = subprocess.call(cmd, shell=True)
    if code:
        sys.exit("❌ Extraction failed. Make sure Babel is installed.")


def update():
    cmd = (
        f'{babel_prefix} update -i "{pot_file_path}" '
        f'-d "{locale_path}" -D {locale_domain} '
        f'--update-header-comment --previous'
    )
    code = subprocess.call(cmd, shell=True)
    if code:
        sys.exit("❌ Failed to update .po files.")


def compile():
    print("⚠️ Make sure translations are updated!")
    prompt = input("Generate .mo now? (Y/N): ")
    if prompt.lower() != "y":
        sys.exit("❌ Cancelled.")

    cmd = (
        f'{babel_prefix} compile -d "{locale_path}" '
        f'-D {locale_domain}'
    )
    code = subprocess.call(cmd, shell=True)
    if code:
        sys.exit("❌ Failed to compile .mo files.")


def main():
    extract()
    update()
    compile()


if __name__ == "__main__":
    main()
