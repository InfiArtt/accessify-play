# noscan
#!/usr/bin/env python3
import os
import sys
import subprocess

cd = os.path.dirname(os.path.abspath(__file__))
locale_path = os.path.join(cd, "locale")  # Changed from "locales" to "locale"
pot_file_path = os.path.join(
    locale_path, "accesifyPlay.pot"
)  # Changed from "messages.pot" to "accesifyPlay.pot"
source_paths = [
    os.path.join(
        cd, "globalPlugins", "accesifyPlay", "__init__.py"
    ),  # Updated to Accessify Play files
    os.path.join(
        cd, "globalPlugins", "accesifyPlay", "spotify_client.py"
    ),  # Updated to Accessify Play files
]

babel_prefix = f'"{sys.executable}" -m babel.messages.frontend'
locale_domain = "accesifyPlay"  # Changed from "messages" to "accesifyPlay"


def extract():
    code = subprocess.call(
        f'{babel_prefix} extract {" ".join(source_paths)} -o "{pot_file_path}" '
        f"--keywords=_ -c translators: --project=AccessifyPlay",  # Changed project name
        shell=True,
    )
    if code:
        sys.exit("❌ Extraction failed. Please make sure Babel is installed.")


def update():
    code = subprocess.call(
        f'{babel_prefix} update -i "{pot_file_path}" -d "{locale_path}" '
        f"-D {locale_domain} --update-header-comment --previous",
        shell=True,
    )
    if code:
        sys.exit("❌ Failed to update .po files.")


def compile():
    print(
        "⚠️ Make sure you've updated the translations for the new strings in the .po file!"
    )
    prompt = input("Do you want to continue and generate the .mo file now? (Y/N): ")
    if prompt.lower() != "y":
        sys.exit(
            "❌ Process cancelled. Please verify the translations before proceeding."
        )

    code = subprocess.call(
        f'{babel_prefix} compile -d "{locale_path}" -D {locale_domain}', shell=True
    )
    if code:
        sys.exit("❌ Failed to compile .mo files.")


def main():
    extract()
    update()
    compile()


if __name__ == "__main__":
    main()
