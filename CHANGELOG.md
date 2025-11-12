# Changelog

## Version 1.3.0 (Unreleased)

- Improvement: Improved the focus behavior in the Search dialog when using the "Load More" feature. Instead of resetting the focus to the top of the list, it now intelligently places the focus on the first of the newly added results. This provides a seamless browsing experience, allowing users to continue exploring search results without losing their place.
- Improvement: Enhanced the stability and reliability of all playback-related shortcuts (Play/Pause, Next/Previous, Seek, and Volume). The addon now prevents sending rapid, overlapping commands to Spotify. If a command is pressed while another is still processing, a "Please wait" message will be announced, ensuring each action completes successfully before the next one is sent.
- Fix: Resolved a crash in the Search dialog that could occur when Spotify's search results contained invalid or empty items. The dialog is now more robust and handles unexpected data gracefully.
- New Feature: Implemented an automatic and manual update system.
    - Checks for updates from GitHub Releases, supporting 'Stable' (main branch) and 'Beta' (dev branch) channels.
    - Automatic checks run silently on NVDA startup (if enabled in settings).
    - Manual checks can be triggered from the settings panel.
    - Displays a pop-up dialog with changelog and an option to download and install new versions.
- New Feature: Added a command to announce the current track's progress and total duration (e.g., "1min 23sec out of 3min 45sec") using the shortcut `NVDA+Alt+Shift+T`.
- Improvement: Dialogs that depend on Spotify data (Management, Queue List, Add to Playlist, etc.) now preload their content before the window appears, eliminating empty states and making loading progress audible.
- Improvement: Added centralized helpers to fetch the current user profile, playlists, saved tracks, saved shows, top items, new releases, and recently played items so the multi-tab Management dialog opens fully populated and refreshes consistently.
- Improvement: Reworked the Search dialog, Management tabs, and Queue window with context menus, keyboard shortcuts, and smarter focus handling so actions like Play/Add to Queue/Copy Link/Follow are discoverable without cluttering the UI.
- Improvement: Standardized the translation bundle to the NVDA `nvda.*` domain, restored the Bahasa Indonesia catalog, and ensured all strings use the correct `.mo` so non-English locales load as expected.
- New Feature: Added a “Follow NVDA language (default)” option plus per-language overrides in the settings panel, letting the add-on keep its own language (e.g., force Bahasa Indonesia) even if NVDA itself stays on another locale.
- Improvement: Management tabs (Manage Playlists, Saved Tracks, Followed Artists, Top Items, Saved Shows, New Releases, Recently Played) now drive all actions through context menus, support Enter-to-play, and offer Copy Link commands for every row.
- New Feature: The Queue dialog exposes a context menu with Play, Copy Link, and Remove actions; removing entries rebuilds the playback queue so you can curate Spotify’s upcoming tracks directly from NVDA.
- Fix: Ensured modal dialogs are destroyed properly when closed (Space, Esc, Alt+F4) so reopening a dialog creates a new instance and reruns the “Playlists loaded” announcement.
- Security: Implemented the more secure Proof Key for Code Exchange (PKCE) authentication flow, replacing the less secure `client_secret` method. This enhances the security of user authentication with Spotify.
- Improvement: Removed the 'Client Secret' field from the Accessify Play settings panel, simplifying the authentication setup process for users.
- Fix: Provided a fallback implementation for the standard Python 'secrets' module, resolving 'ModuleNotFoundError' issues in environments with older Python versions and improving addon compatibility.
- New Feature: Implemented a "Migrate Old Credentials" button in the Accessify Play settings panel. This button appears if old Client ID or Secret Key data is detected in NVDA's configuration, allowing users to seamlessly migrate their Client ID to the new portable storage location and remove obsolete credentials.
- New Feature: Added a "Go to Developer Dashboard" button to the Accessify Play settings panel, providing quick access to the Spotify Developer Dashboard for managing Client IDs.

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
