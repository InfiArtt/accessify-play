# Changelog

## Version 1.4.0

This is a significant feature and stability release, focused on improving user workflow, adding powerful new capabilities, and enhancing overall reliability.

#### ✨ New Features

-   **Add to Playlist from Search**: You can now add a track directly to one of your playlists from the search results context menu. (Resolves #22)
-   **Richer Artist Browsing**: The artist discography dialog has been enhanced with new tabs for "Artist Info" and "All Tracks," featuring incremental loading to handle large discographies efficiently.
-   **Quick Playlist Playback**: A "Play Playlist" button has been added next to the playlist selection dropdown in the Management dialog, allowing for immediate playback of the selected playlist.
-   **Delete Track with Keyboard**: In the Management dialog's playlist tab, you can now press the `Delete` key on a selected track to remove it from the playlist (after a confirmation prompt).
-   **Pagination for Large Catalogs**: "Load More" functionality has been added to long lists, such as playlist tracks and podcast episodes. This respects the "Search Results Limit" setting and significantly reduces initial load times.
-   **Proactive Device Wake-Up**: The addon now automatically attempts to "wake up" the last used Spotify device if it becomes inactive. This resolves many "No active device found" errors, making playback resumption smoother. (Resolves #25)

#### 🛠️ Fixes & Improvements

-   **Enhanced Search Activation**: Pressing `Enter` on artists, albums, podcasts, or playlists in the search results now opens the appropriate detailed view (e.g., discography, track list) instead of immediately starting playback. This creates a more consistent and predictable exploration workflow. (Resolves #19)
-   **Improved Shortcut Implementation**: All UI shortcuts now function consistently across the interface, with clearer usage in search, management, and queue.
-   **Reliable Skip Commands**: The next/previous track shortcuts now verify a follow-up track exists before executing and translate Spotify's restriction errors into friendly messages (e.g., "No previous track available."). This prevents playback from stopping unexpectedly. (Resolves #23)
-   **Accurate Playback Announcements**: The scripts for announcing the current track and "next in queue" now respect Spotify’s `is_playing` flag and handle empty queues correctly, preventing stale or inaccurate announcements.
-   **Smarter Queue Management**: Queueing an album or playlist is now more reliable. The "currently playing" item in the queue dialog is now hidden when playback stops, accurately reflecting the current state.
-   **Episode Playback Fix**: Corrected Spotify URI handling so that individual podcast episodes play reliably without errors.
-   **Code Reorganization**: The addon's codebase has been reorganized into separate files for each dialog/class. This improves maintainability, simplifies error tracking, and makes future development easier.

## Version 1.3.4

#### Code Fixes
-   **Improved Updater Version Parsing**: Fixed an issue where the updater could not correctly parse and compare semantic versions that included pre-release tags (e.g., `1.3.5-pre`, `1.3.5-beta1`, `1.3.5-rc4`). The version parsing logic has been updated to accurately handle these formats, ensuring that the addon correctly identifies and offers the latest available updates across all release channels.

## Version 1.3.3

This is a maintenance and code quality release that addresses significant structural issues from previous versions. The primary focus is on refactoring duplicated code, cleaning up logic, and improving the overall stability and long-term maintainability of the addon.

#### ✨ Improvements & Refinements

-   **Unified Language System**: The language management system has been completely unified and centralized. The addon now correctly follows NVDA's default language and provides a seamless fallback to English if a translation is not available. The language selection dropdown in the settings panel is now dynamically populated, ensuring all available languages are always displayed correctly.
-   **Default Port Change**: The default callback port for Spotify authentication has been changed from `8888` to `8539`. This helps prevent potential conflicts with other applications that may use port 8888. New installations will use this port by default.
#### 🛠️ Code Fixes & Housekeeping

-   **Improved Updater Version Parsing**: Fixed an issue where the updater could not correctly parse and compare semantic versions that included pre-release tags (e.g., `1.3.5-pre`, `1.3.5-beta1`, `1.3.5-rc4`). The version parsing logic has been updated to accurately handle these formats, ensuring that the addon correctly identifies and offers the latest available updates across all release channels.
-   **Major Code Refactoring**: Removed a large block of duplicated code within the addon's main file (`__init__.py`). This resolves the primary source of instability from version 1.3.1/1.3.2 and makes the addon significantly easier to maintain and debug.
-   **Corrected Settings Logic**: Fixed a bug in the settings panel (`onSave` method) where the selected language was not being saved correctly due to an incorrect variable name.
-   **Cleaned Up UI Logic**: Resolved a minor error in the settings panel that would occur when clearing credentials, which was caused by referencing a non-existent UI element.
-   **Removed Redundant Imports**: Cleaned up duplicated and unnecessary module imports for a slightly leaner and more organized codebase.

## Version 1.3.2 (Required Hotfix)

This is an essential hotfix release to address a critical bug that prevented credential validation in version 1.3.1. This update is solely focused on restoring core functionality.

#### 🛠️ Critical Fix

-   **Restored Credential Validation**: Fixed a critical `AttributeError` that occurred when pressing the "Validate Credentials" button in the settings panel. This bug made it impossible for users to authenticate with Spotify. With this fix, the validation process now works as expected, allowing the addon to be used.

#### 📝 Developer Notes

-   **Code Quality**: Please be aware that this release contains known code duplication and other structural issues. The immediate priority was to fix the validation bug.
-   **Future Cleanup**: A follow-up release (version 1.3.3 or newer) is planned to address these underlying code quality problems, refactor duplicated logic, and ensure long-term stability.


## Version 1.3.1

This is a major release focusing on security, usability, and new features, representing the most significant update to the addon yet.

#### ✨ New Features

- **Automatic & Manual Updater**: The addon can now check for updates directly from GitHub. Enable automatic checks on NVDA startup or trigger them manually from the settings panel, with support for `Stable` and `Beta` release channels.
- **Announce Playback Time**: A new command (`NVDA+Alt+Shift+T`) announces the current track's progress and total duration (e.g., "1min 23sec out of 3min 45sec").
- **Advanced Queue Management**: The Queue dialog now features a context menu with `Play`, `Copy Link`, and `Remove` actions. Removing an item rebuilds Spotify's playback queue, giving you direct control over upcoming tracks.
- **Flexible Language Options**: You can now have the addon follow NVDA's language or override it with a specific language (e.g., keep the addon in English even if NVDA is set to another locale).
- **Seamless Credential Migration**: A "Migrate Old Credentials" button now appears in settings if legacy `Client ID` or `Client Secret` data is found, allowing for a one-click migration to the new, more secure storage system.
- **Quick Developer Access**: A "Go to Developer Dashboard" button has been added to the settings panel for easy access to manage your Spotify Client ID.

#### 🔐 Security Enhancements

- **Modernized PKCE Authentication**: The addon now uses Spotify's more secure **Proof Key for Code Exchange (PKCE)** authentication flow. This significantly enhances security and **removes the need for a `Client Secret`**, simplifying the setup process.

#### 🚀 Improvements

- **Enhanced User Interface & Experience**:
  - **Context Menus Everywhere**: All lists (Search Results, Saved Tracks, Queue, etc.) now feature context menus for quick access to actions like `Play`, `Add to Queue`, `Copy Link`, and more, creating a cleaner and more powerful UI.
  - **Smarter Focus Handling**: When using "Load More" in the Search dialog, focus is now intelligently moved to the first new result, enabling a seamless browsing experience without losing your place.
  - **Responsive Data Loading**: Dialogs that rely on Spotify data (like Management and Queue) now preload content *before* appearing, providing a faster and more fluid user experience.
- **Reliable Playback Commands**: All playback-related shortcuts (Play/Pause, Next/Previous, Volume, etc.) are now more stable. The addon prevents overlapping commands; if a shortcut is pressed while another is processing, a "Please wait..." message is announced, ensuring each action completes successfully.
- **Full Internationalization Support**: The translation system has been standardized, ensuring that all text is translatable and that non-English locales (including Bahasa Indonesia) load correctly.

#### 🛠️ Fixes

- **Podcast & Show Information Now Works**: Fixed a critical issue where information for currently playing podcasts or shows could not be retrieved. The addon can now correctly identify and announce details for both music tracks and podcast episodes.
- **Search Dialog Stability**: Resolved a crash that could occur if Spotify's search results contained invalid or empty data.
- **Dialog Management**: Ensured all dialogs are properly destroyed when closed, so reopening them always presents fresh data.

## Version 1.2.0

- New Feature: Set Specific Volume: Added a dialog to set the Spotify volume to a precise percentage (0-100) using the shortcut NVDA+Shift+Alt+V.
- New Feature: Comprehensive Library Management: Introduced a new multi-tabbed "Management" dialog (NVDA+Alt+Shift+M) for full control over your Spotify library.
    - Manage Playlists: View tracks within your playlists, update playlist details, delete playlists, and remove tracks from a playlist.
    - Create Playlist: A new tab to create new public or private playlists with a description.
    - Saved Tracks: View all your "Liked Songs" and remove them directly from the list.
    - Followed Artists: View all followed artists with options to play, unfollow, or view their discography.
    - Top Items: Discover your top-played tracks and artists over different time periods (4 weeks, 6 months, all time).
    - Saved Shows: View your saved podcasts and browse their episodes.
    - New Releases: Browse the latest album and single releases on Spotify.
- New Feature: Quick Save to Library: Added a command to quickly save the currently playing track to your "Liked Songs" (NVDA+Alt+Shift+L).
- New Feature: Quick Add to Playlist: Added a command to add the currently playing track to one of your playlists via a selection dialog (NVDA+Alt+Shift+A).
- New Feature: Automatic Track Announcements: Added an optional setting to have NVDA automatically announce the new track whenever the song changes.
- New Feature: Artist and Podcast Discovery:
    - Added an Artist Discography dialog to view top tracks and albums.
    - Added a Podcast Episodes dialog to browse all episodes of a show.
- New Feature: Language Selection: Added an option in the settings to change the add-on's language (English or Bahasa Indonesia, though it is not working right now).
- Fix: Corrected a critical indentation error in spotify_client.py that prevented several API calls (like getting artist albums and related artists) from working.
- Fix (Accessibility): Ensured labels for checkboxes in the Settings and Create Playlist panels are integrated directly into the control, making them readable by NVDA.

## Version 1.0.1

- New Feature: Added a command to announce the next track in the Spotify queue (NVDA+Shift+Alt+N).
- New Feature: Implemented a dialog to show the full Spotify queue, allowing users to view and play selected items (NVDA+Shift+Alt+Q).
- New Feature: Added commands to seek forward (Control+Alt+NVDA+RightArrow) and backward (Control+Alt+NVDA+LeftArrow) in the current track.
- Improvement: The seek forward/backward duration is now configurable via the Accessify Play settings (default 15 seconds).
- New Feature: Added a "Clear Credentials" button in the Accessify Play settings panel, allowing users to clear their Spotify API credentials and delete the token cache with a confirmation prompt.
- Improvement: Changed the storage location of spotify_token_cache.json to %USERPROFILE%\.spotify_cache.json for enhanced portability and security, separating it from NVDA's configuration.
- Fix: Resolved sys.sys.path typo in __init__.py that prevented the addon from loading correctly.
- Fix: Corrected AttributeError: 'Spotify' object has no attribute 'current_user_queue' by using the proper spotipy.client.queue method.
- Fix: Addressed SyntaxError in spotify_client.py caused by a corrupted replace operation during development.

## Version 1.0.0

- New Feature: Added a dialog to play a track from a shared Spotify URL (NVDA+Shift+Alt+P).
- New Feature: Added a command to copy the current track's Spotify URL to the clipboard (NVDA+Shift+Alt+C).
- New Feature: Added an enhanced search dialog (NVDA+Shift+Alt+S) with filtering by type (song, album, etc.) and a "Load More" option for results.
- New Feature: Added a command to announce the currently playing song, artist, and album (NVDA+Shift+Alt+I).
- Improvement: Added settings to configure the callback port and the search result limit.
- Improvement: The search dialog now displays the owner's name for playlist results.
- Improvement: The addon now automatically re-authenticates when NVDA restarts if it has been validated once, removing the need to re-validate every session.
- Improvement: Added a "Validate Credentials" button in the settings panel for immediate feedback on the configuration.
- Fix: Corrected addon structure to prevent load errors and ensure third-party libraries are imported correctly.
- Fix: Improved error messages to better guide users when their Spotify Developer App is misconfigured.
