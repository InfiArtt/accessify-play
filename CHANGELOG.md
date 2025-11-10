# Changelog

## Version 1.3.0 (Unreleased)
- Improvement: Dialogs that depend on Spotify data (Management, Queue List, Add to Playlist, etc.) now preload their content before the window appears, eliminating empty states and making loading progress audible.
- Improvement: Added centralized helpers to fetch the current user profile, playlists, saved tracks, saved shows, top items, new releases, and recently played items so the multi-tab Management dialog opens fully populated and refreshes consistently.
- Fix: Resolved multiple tab/spaces indentation issues that previously prevented the add-on from loading and caused TabErrors in both `__init__.py` and `spotify_client.py`.
- Fix: Ensured modal dialogs are destroyed properly when closed (Space, Esc, Alt+F4) so reopening a dialog creates a new instance and reruns the “Playlists loaded” announcement.

## Version 1.2.0 (Unreleased)

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

## Version 1.0.1 (Unreleased)

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
