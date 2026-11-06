# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Checks on the project rather than the code: catalogues, user guides, conventions and packaging."""

from __future__ import annotations

import ast
import io
import re
import string
import subprocess
import tokenize
from functools import cache
from pathlib import Path

import pytest
from accesifyPlay.commands import COMMANDS
from accesifyPlay.settings_spec import SETTINGS
from babel.messages.catalog import Catalog
from babel.messages.extract import extract_from_file
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "addon"
PKG = ADDON / "globalPlugins" / "accesifyPlay"
DOC = ADDON / "doc"
LIB = ADDON / "lib"
LANGS = ("en", "id")
KEYWORDS = {"_": None, "ngettext": (1, 2), "pgettext": ((1, "c"), 2), "npgettext": ((1, "c"), 2, 3)}


def read(path: Path) -> str:
	"""Return a file's text."""
	return path.read_text(encoding="utf-8")


def package_sources() -> list[Path]:
	"""Return every Python file of the add-on's own package."""
	return sorted(path for path in PKG.rglob("*.py") if "__pycache__" not in path.parts)


# --- Translations -----------------------------------------------------------------------------


@cache
def code_strings() -> frozenset[str]:
	"""Return every translatable string in the code, as xgettext would find it."""
	catalog = Catalog(project="AccessifyPlay")
	for path in [ROOT / "buildVars.py", ADDON / "installTasks.py", *package_sources()]:
		for lineno, message, comments, context in extract_from_file(
			"python", str(path), keywords=KEYWORDS, comment_tags=("Translators:",)
		):
			catalog.add(message, locations=[(str(path), lineno)], auto_comments=comments, context=context)
	return frozenset(message.id for message in catalog if message.id)


@cache
def catalog(language: str) -> Catalog:
	"""Return a language's catalogue as it is in the repository."""
	with (ADDON / "locale" / language / "LC_MESSAGES" / "nvda.po").open("rb") as po:
		return read_po(po)


def translations() -> dict[str, str]:
	"""Return the Indonesian catalogue as msgid -> translation."""
	return {message.id: message.string for message in catalog("id") if message.id}


def test_every_string_is_translated() -> None:
	"""Each translatable string in the code is in the Indonesian catalogue and translated.

	Only the store changelog of each release (buildVars.py) may wait for a translation.
	"""
	entries = translations()
	missing = sorted(code_strings() - set(entries))
	assert not missing, f"not in the Indonesian catalogue: {missing[:5]}"
	untranslated = sorted(i for i in code_strings() if not entries[i] and not str(i).startswith("\n- "))
	assert not untranslated, f"not translated: {untranslated[:5]}"


def test_the_catalogue_holds_nothing_else() -> None:
	"""No obsolete or fuzzy entries: msgfmt would skip a fuzzy one."""
	assert not catalog("id").obsolete
	assert set(translations()) <= code_strings(), sorted(set(translations()) - code_strings())[:5]
	assert not [message.id for message in catalog("id") if message.id and "fuzzy" in message.flags]


def test_the_english_catalogue_is_the_template() -> None:
	"""The English catalogue lists the same strings, untranslated."""
	english = catalog("en")
	assert {message.id for message in english if message.id} == code_strings()
	assert not [message.id for message in english if message.id and message.string]


def test_the_catalogue_compiles_and_translates() -> None:
	"""It compiles to a .mo file, and gettext answers in Indonesian."""
	import gettext  # noqa: PLC0415 - only this test needs it

	buffer = io.BytesIO()
	write_mo(buffer, catalog("id"))
	buffer.seek(0)
	indonesian = gettext.GNUTranslations(buffer)
	assert indonesian.gettext("Show Lyrics") == "Tampilkan Lirik"
	assert indonesian.gettext("&Close") == "&Tutup"


def test_every_translation_formats_like_the_original() -> None:
	"""A translation takes exactly the placeholders of its English text, so .format() never fails."""
	bad = []
	for msgid, msgstr in translations().items():
		if not isinstance(msgid, str) or not msgstr:
			continue
		fields = [field for _, field, _, _ in string.Formatter().parse(msgid) if field is not None]
		named = {field: "X" for field in fields if field}
		positional = ["X"] * fields.count("")
		try:
			msgstr.format(*positional, **named)
		except (KeyError, IndexError, ValueError):
			bad.append(msgid)
	assert not bad, bad[:5]


def test_menu_shortcuts_and_mnemonics() -> None:
	"""Shortcuts after a tab stay as they are; the lyrics window's Alt letters stay distinct."""
	entries = translations()
	for msgid, msgstr in entries.items():
		if isinstance(msgid, str) and "\t" in msgid and msgstr:
			assert msgstr.split("\t")[1] == msgid.split("\t")[1], msgid
	keys = ("&Close", "Copy &Lyrics", "Copy with &Timestamps", "&Jump to Current")
	letters = [re.search(r"&(\w)", entries[key]).group(1).upper() for key in keys]
	assert len(set(letters)) == len(letters), letters


@pytest.mark.parametrize("language", LANGS)
def test_catalogue_encoding(language: str) -> None:
	"""UTF-8, and one kind of line ending (CRLF in a Windows checkout, LF elsewhere)."""
	raw = (ADDON / "locale" / language / "LC_MESSAGES" / "nvda.po").read_bytes()
	raw.decode("utf-8")
	assert raw.count(b"\r\n") in (0, raw.count(b"\n"))


# --- User guides ------------------------------------------------------------------------------


def pages(language: str) -> list[str]:
	"""Return the names of a language's guide pages."""
	return sorted(path.name for path in (DOC / language).glob("*.md"))


def guide(language: str, page: str) -> str:
	"""Return one page of a guide."""
	return read(DOC / language / page)


#: Text about setups and shortcuts the add-on no longer has.
STALE = (
	"Client ID is correct",
	"Callback Port",
	"8888",
	"8539",
	"NVDA+Shift+Alt",
	"NVDA+Alt+Shift",
	"NVDA+G`",
	"Migrate Old Credentials",
	"Check for Updates",
	"Update Channel",
	"related artists",
	"Related Artists",
	"auto-update",
)


def tracked(folder: Path) -> list[str]:
	"""Return the files git keeps under folder; a local build adds others that .gitignore leaves out."""
	result = subprocess.run(  # noqa: S603 - a fixed git command on our own repository
		["git", "-C", str(ROOT), "ls-files", folder.relative_to(ROOT).as_posix()],  # noqa: S607 - git from PATH
		capture_output=True,
		text=True,
		check=False,
	)
	if result.returncode:
		pytest.skip("not a git checkout")
	return result.stdout.splitlines()


def test_both_languages_have_the_same_pages() -> None:
	"""Same pages in English and Indonesian, readme.md among them, and no generated HTML committed."""
	assert pages("en") == pages("id")
	assert "readme.md" in pages("en")
	assert not [name for name in tracked(DOC) if name.endswith(".html")]


@pytest.mark.parametrize("language", LANGS)
def test_links_between_pages(language: str) -> None:
	"""Every link to another page resolves, and every page is linked from another one."""
	texts = {page: guide(language, page) for page in pages(language)}
	for page, text in texts.items():
		for target in re.findall(r"\]\(([^)#:]+\.html)\)", text):
			assert (DOC / language / f"{target[:-5]}.md").exists(), f"{language}/{page} links to {target}"
	for page in pages(language):
		if page != "readme.md":
			assert any(f"{page[:-3]}.html" in text for other, text in texts.items() if other != page), page


@pytest.mark.parametrize("language", LANGS)
def test_no_stale_content(language: str) -> None:
	"""No page describes a setup or a shortcut that is gone."""
	for page in pages(language):
		text = guide(language, page)
		assert not [word for word in STALE if word in text], f"{language}/{page}"


def layer_keys() -> set[str]:
	"""Return the command layer's default keys, plus F1, F2 and Escape, as the guides write them."""
	return {command.key.removeprefix("kb:").upper() for command in COMMANDS} | {"F1", "F2", "ESCAPE"}


@pytest.mark.parametrize("language", LANGS)
def test_keybindings_list_the_layer(language: str) -> None:
	"""keybindings.md lists exactly the layer's keys, and marks exactly the ones that keep it open."""
	text = guide(language, "keybindings.md")
	listed = {key.upper() for key in re.findall(r"^\| `([^`]+)` \|", text, re.MULTILINE)}
	assert listed == layer_keys()
	stays = re.findall(r"^\| `([^`]+)` \|[^|]*\((?:stays open|tetap terbuka)\)", text, re.MULTILINE)
	keep_open = {command.key.removeprefix("kb:").upper() for command in COMMANDS if command.keep_open}
	assert {key.upper() for key in stays} == keep_open


def test_the_readme() -> None:
	"""README.md's key table covers the layer, and it points to the Add-on Store and the notices."""
	readme = read(ROOT / "README.md")
	keys = {key.upper() for key in re.findall(r"\| `([^`]+)` \|", readme)}
	keys |= {key.upper() for pair in re.findall(r"\| `([^`]+)` / `([^`]+)` \|", readme) for key in pair}
	assert not layer_keys() - {"ESCAPE"} - keys
	assert "NVDA+Shift+Alt" not in readme
	assert "lint.yml" not in readme
	for text in (readme, guide("en", "readme.md")):
		assert "Add-on Store" in text
	assert "addon/thirdPartyNotices.md" in readme


def test_the_guide_matches_the_build() -> None:
	"""The minimum NVDA version, tables, the guide itself and no compiled files in the package."""
	build = read(ROOT / "buildVars.py")
	minimum = re.search(r'addon_minimumNVDAVersion="([^"]+)"', build).group(1)
	for language in LANGS:
		assert f"NVDA {minimum}" in guide(language, "readme.md")
	assert '"markdown.extensions.tables"' in build
	assert '"*.pyc"' in build
	assert 'Path("readme.md")' not in read(ROOT / "sconstruct")
	# The tests import the add-on before CI builds it; they must not leave __pycache__ behind.
	assert 'PYTHONDONTWRITEBYTECODE: "1"' in read(ROOT / ".github" / "workflows" / "build_addon.yml")


# --- Conventions in the code ------------------------------------------------------------------


def test_the_spec_is_registered_before_any_other_module() -> None:
	"""__init__ registers the config spec before importing any add-on module but settings_spec.

	Importing one can evaluate _() at class-body level, which reads the
	[spotify] section; read before the spec, it loses its defaults (1.10.0).
	"""
	lines = read(PKG / "__init__.py").splitlines()
	spec_line = next(i for i, line in enumerate(lines) if line.startswith('config.conf.spec["spotify"]'))
	imports = [i for i, line in enumerate(lines) if re.match(r"\s*from \.", line)]
	early = [lines[i] for i in imports if i < spec_line]
	assert early == ["from .settings_spec import CONFSPEC, conf_get"]


def test_modules_that_load_first_stay_simple() -> None:
	"""settings_spec translates nothing and imports no add-on module; thread_manager reads no settings."""
	tree = ast.parse(read(PKG / "settings_spec.py"))
	imported = {
		node.module if isinstance(node, ast.ImportFrom) else alias.name
		for node in ast.walk(tree)
		if isinstance(node, (ast.Import, ast.ImportFrom))
		for alias in node.names
	}
	assert imported == {"__future__", "dataclasses", "config", "logHandler"}
	assert "config.conf" not in read(PKG / "core" / "thread_manager.py")


def _setting_names(node: ast.AST) -> set[str]:
	"""Return the setting named by one node, if it names one: conf_get("x"), spotify["x"], ..."""
	# Shortcut settings (keyPlay, ...) are named wherever a window binds or shows one.
	if (
		isinstance(node, ast.Constant)
		and isinstance(node.value, str)
		and re.fullmatch(r"key[A-Z]\w*", node.value)
	):
		return {node.value}
	if isinstance(node, ast.Call):
		called = getattr(node.func, "id", getattr(node.func, "attr", None))
		position = {"conf_get": 0, "_add_spin": 1, "_add_choice": 1}.get(called)
		if position is not None and len(node.args) > position:
			argument = node.args[position]
			return {argument.value} if isinstance(argument, ast.Constant) else set()
		# The .get() on the section that language.py uses, so it never creates it.
		if called == "get" and isinstance(node.func.value, ast.Subscript) and node.args:
			return _setting_names(ast.Subscript(node.func.value, node.args[0]))
	if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
		section = node.value
		# A key of the [spotify] section itself, or of the panel's local name for it.
		in_spotify = getattr(section, "id", None) == "spotify" or (
			isinstance(section, ast.Subscript) and getattr(section.slice, "value", None) == "spotify"
		)
		return {node.slice.value} if in_spotify else set()
	return set()


def settings_read() -> set[str]:
	"""Return every setting the add-on reads or writes by name."""
	# Not the table itself, which names every setting.
	return {
		name
		for path in package_sources()
		if path.name != "settings_spec.py"
		for node in ast.walk(ast.parse(read(path)))
		for name in _setting_names(node)
	}


def test_every_setting_is_used_and_every_used_setting_exists() -> None:
	"""No setting in the table goes unread, and the code reads no setting the table lacks."""
	used = settings_read()
	assert used - set(SETTINGS) == set()
	assert set(SETTINGS) - used == set()


def test_no_translatable_text_inside_an_f_string() -> None:
	"""Babel and xgettext cannot see _() inside an f-string, so that text would never be translated."""
	hidden = []
	for path in package_sources():
		for token in tokenize.generate_tokens(io.StringIO(read(path)).readline):
			is_f_string = token.type == tokenize.STRING and re.match(r"(?i)[rb]*f", token.string)
			if is_f_string and re.search(r"\b_\(", token.string):
				hidden.append(f"{path.name}:{token.start[0]}")
	assert not hidden


@pytest.mark.parametrize(
	("module", "label"),
	[
		("devices.py", "Devices:"),
		("layer_editor.py", "Commands:"),
		("lyrics_window.py", "Lyrics:"),
		("management.py", "Tracks:"),
		("management.py", "Items:"),
		("queue_list.py", "Queue:"),
	],
)
def test_lists_are_named_by_the_label_before_them(module: str, label: str) -> None:
	"""NVDA names a list or field after the static text created right before it."""
	source = read(PKG / "dialogs" / module)
	start = source.find(f'label=_("{label}")')
	assert start >= 0
	following = source.find("wx.", source.find("\n", start))
	assert re.match(r"wx\.(ListBox|ListCtrl|TextCtrl)\(", source[following:])


# --- Packaging --------------------------------------------------------------------------------


def bundled() -> list[tuple[str, str, Path]]:
	"""Return (name, version, dist-info folder) for each library in addon/lib."""
	found = []
	for info in sorted(LIB.glob("*.dist-info")):
		metadata = read(info / "METADATA")
		name = re.search(r"^Name: (.+)$", metadata, re.MULTILINE).group(1).strip()
		version = re.search(r"^Version: (.+)$", metadata, re.MULTILINE).group(1).strip()
		found.append((name, version, info))
	return found


def test_every_bundled_library_is_credited() -> None:
	"""The third-party notices list each library with the version bundled, and its licence text is there."""
	notices = read(ADDON / "thirdPartyNotices.md")
	assert bundled()
	for name, version, info in bundled():
		row = next(
			(line for line in notices.splitlines() if line.lower().startswith(f"| {name.lower()} |")), ""
		)
		assert f"| {version} |" in row, name
		assert list((info / "licenses").iterdir()), name
	assert "_secrets_fallback.py" in notices


def test_the_secrets_fallback_is_installed_first() -> None:
	"""Nothing in lib can be imported as secrets, and __init__ installs the fallback before spotipy loads."""
	assert not (LIB / "secrets.py").exists()
	assert not (LIB / "secrets").exists()
	source = read(PKG / "__init__.py")
	assert source.index("_install_secrets()") < source.index("\tspotify_client,")
