# Build customizations
# Change this file instead of sconstruct or manifest files, whenever possible.

from site_scons.site_tools.NVDATool.typings import AddonInfo, BrailleTables, SymbolDictionaries

# Since some strings in `addon_info` are translatable,
# we need to include them in the .po files.
# Gettext recognizes only strings given as parameters to the `_` function.
# To avoid initializing translations in this module we simply import a "fake" `_` function
# which returns whatever is given to it as an argument.
from site_scons.site_tools.NVDATool.utils import _


# Add-on information variables
addon_info = AddonInfo(
	# add-on Name/identifier, internal for NVDA
	addon_name="AccessifyPlay",
	# Add-on summary/title, usually the user visible name of the add-on
	# Translators: Summary/title for this add-on
	# to be shown on installation and add-on information found in add-on store
	addon_summary=_("Accessify Play"),
	# Add-on description
	# Translators: Long description to be shown for this add-on on add-on information from add-on store
	addon_description=_("""Accessify Play provides comprehensive NVDA control for Spotify playback on any Connect-enabled device. A Spotify Premium subscription is required for full functionality."""),
	# version
	addon_version="1.12.1",
	# Brief changelog for this version
	# Translators: what's new content for the add-on version to be shown in the add-on store
	addon_changelog=_("""
- 1.12.1: a smaller download; the 1.12.0 package accidentally contained compiled files.
- Updates now come from the NVDA Add-on Store; the built-in updater has been removed.
- Settings, Copy Universal Link and Sleep Timer can now be given a shortcut in Input Gestures.
- Announce track (I) names the track and says it is paused, instead of "Nothing is currently playing".
- Top Items updates as soon as you change Show or Time Range.
- Set Volume starts at the current volume; Alt+F in Search follows or unfollows an artist.
- The sleep timer tells you when it pauses the music.
- Fixed Help opening an outdated guide, and the lyrics window failing the second time for the same song.
- Show Lyrics, Go to Album and Go to Artist in album and playlist track lists.
- Names for unlabeled controls in Search, Devices, Queue, episode, chapter and other lists.
- Complete and corrected Indonesian translation, and a rewritten user guide.
	"""),
	# Author(s)
	addon_author="Rafli I .<rafli08523717409@gmail.com>, Rexya <rexya2017@gmail.com>",
	# URL for the add-on documentation support
	addon_url="https://github.com/InfiArtt/accessify-play",
	# URL for the add-on repository where the source code can be found
	addon_sourceURL="https://github.com/InfiArtt/accessify-play",
	# Documentation file name
	addon_docFileName="readme.html",
	# Minimum NVDA version supported (e.g. "2019.3.0", minor version is optional)
	addon_minimumNVDAVersion="2025.1",
	# Last NVDA version supported/tested (e.g. "2024.4.0", ideally more recent than minimum version)
	addon_lastTestedNVDAVersion="2026.1",
	# Add-on update channel (default is None, denoting stable releases,
	# and for development releases, use "dev".)
	# Do not change unless you know what you are doing!
	addon_updateChannel=None,
	# Add-on license such as GPL 2
	addon_license="GNU General Public License, version 2 or later",
	# URL for the license document the ad-on is licensed under
	addon_licenseURL="https://www.gnu.org/licenses/gpl-2.0.html",
)

# Define the python files that are the sources of your add-on.
# You can either list every file (using ""/") as a path separator,
# or use glob expressions.
# This expression includes all .py files in the accesifyPlay folder and its subdirectories.
pythonSources: list[str] = [
    "addon/globalPlugins/accesifyPlay/**/*.py",
    "addon/installTasks.py"
]

# Files that contain strings for translation. Usually your python sources
i18nSources: list[str] = pythonSources + ["buildVars.py"]

# Files that will be ignored when building the nvda-addon file
# Paths are relative to the addon directory, not to the root directory of your addon sources.
# You can either list every file (using ""/") as a path separator,
# or use glob expressions.
# Bytecode written while running the tests must never end up in the package.
excludedFiles: list[str] = ["*.pyc"]

# Base language for the NVDA add-on
# If your add-on is written in a language other than english, modify this variable.
# For example, set baseLanguage to "es" if your add-on is primarily written in spanish.
# You must also edit .gitignore file to specify base language files to be ignored.
baseLanguage: str = "en"

# Markdown extensions for add-on documentation
# Most add-ons do not require additional Markdown extensions.
# If you need to add support for markup such as tables, fill out the below list.
# Extensions string must be of the form "markdown.extensions.extensionName"
# e.g. "markdown.extensions.tables" to add tables.
markdownExtensions: list[str] = ["markdown.extensions.tables"]

# Custom braille translation tables
# If your add-on includes custom braille tables (most will not), fill out this dictionary.
# Each key is a dictionary named according to braille table file name,
# with keys inside recording the following attributes:
# displayName (name of the table shown to users and translatable),
# contracted (contracted (True) or uncontracted (False) braille code),
# output (shown in output table list),
# input (shown in input table list).
brailleTables: BrailleTables = {}

# Custom speech symbol dictionaries
# Symbol dictionary files reside in the locale folder, e.g. `locale\en`, and are named `symbols-<name>.dic`.
# If your add-on includes custom speech symbol dictionaries (most will not), fill out this dictionary.
# Each key is the name of the dictionary,
# with keys inside recording the following attributes:
# displayName (name of the speech dictionary shown to users and translatable),
# mandatory (True when always enabled, False when not.
symbolDictionaries: SymbolDictionaries = {}
