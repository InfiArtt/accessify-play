# Sign-in and settings

All of Accessify Play's settings are in NVDA's Settings dialog: open the NVDA menu (`NVDA+N`), then Preferences, Settings, and choose **Accessify Play**. From the command layer, `NVDA+Alt+G` then `F4` opens it directly.

## Signing in to Spotify

Press **Validate Credentials**. Your web browser opens a Spotify page asking you to allow Accessify Play to use your account; agree to it. Back in NVDA you will hear "Validation successful!".

You only need to do this once. Accessify Play remembers the sign-in, and Spotify renews it automatically.

If signing in fails, make sure you finished signing in in the browser and that you are connected to the internet, then press Validate Credentials again.

> If you have used Accessify Play before version 1.9.0: you no longer need your own Spotify developer app, Client ID or callback port. Signing in is all it takes. Using your own Client ID is still possible, but optional; see below.

**Clear Credentials** signs you out: it deletes the stored Spotify sign-in from this computer, after asking you to confirm. Use Validate Credentials to sign in again, for example with a different account.

## Using your own Client ID (optional)

Out of the box, everyone signs in through the same shared Spotify Client ID, so nobody has to set anything up. Spotify limits how many requests one Client ID may send, and everyone using the shared one shares that limit. If you often hear "Spotify is limiting requests at the moment", or the shared Client ID ever stops working, you can use a Client ID of your own instead:

1. Press **Spotify Developer Dashboard** in Accessify Play's settings, and sign in with your Spotify account.
2. Create an app. Any name and description will do. Under Redirect URIs add exactly `http://127.0.0.1:5588/login`, and under the APIs it uses choose **Web API**. Accept Spotify's terms and save.
3. Open the app's settings and copy its **Client ID**, 32 letters and digits.
4. Paste it into **Your own Spotify Client ID** in Accessify Play's settings, and press **Validate Credentials** to sign in with it.

Spotify's own rules for developer apps apply to an app you create. To go back to the shared Client ID, empty the field and press OK. Accessify Play keeps a separate sign-in for each, so switching back and forth does not make you sign in again.

## Settings

* **Search Results Limit (1 to 50)**: how many results Search shows at a time, 20 by default. Lists of episodes, chapters and playlist tracks load in pages of the same size, with a "Load More" item at the end.
* **Seek Duration (seconds, 1 to 60)**: how far Seek Forward and Seek Backward jump, 15 seconds by default.
* **Volume Step (1 to 100)**: how much Volume Up and Volume Down change the volume, 5% by default.
* **Keep Alive Interval (seconds, 0 = Off, Min = 5)**: how often Accessify Play checks in with Spotify in the background, so the first command after a quiet period responds quickly, up to 3600 seconds. Off (0) by default, since every check counts against the request limit Accessify Play shares with everyone who uses it; turn it on only if the first command after a pause is noticeably slow for you. Values from 1 to 4 are raised to 5.
* **Sleep timer starts at (minutes, 1 to 1440)**: the number of minutes the sleep timer offers when you open it, 30 by default.
* **Longest sleep timer (minutes, 1 to 1440)**: the most minutes the sleep timer accepts, 240 (four hours) by default.
* **Most tracks to queue from an album or playlist (1 to 1000)**: Add to Queue on a whole album or playlist sends one request for every track, and every request counts against the shared request limit. So it queues at most this many tracks, 100 by default, and says so when it stops early.
* **Play My Top Tracks plays the top tracks of**: the period `G` in the command layer takes its tracks from: Last 4 Weeks (the default), Last 6 Months or All Time.
* **Top Items in the Library opens on**: the Time Range the Library's Top Items tab starts with, Last 6 Months by default.
* **Search opens on**: the Type the Search window starts with, Song by default.
* **Language**: the language of Accessify Play's messages and dialogs. "Follow NVDA language (default)" uses NVDA's language; you can also choose English or Bahasa Indonesia regardless of NVDA's language. A change takes effect after restarting NVDA.
* **Announce track changes automatically**: when checked, NVDA announces each new track (or episode) as it starts, wherever it was started from.
* **New playlists are public**: whether Public playlist is checked when you create a playlist. Checked by default.
* **Your own Spotify Client ID (optional, leave blank to use the shared one)**: see "Using your own Client ID" above.

## Buttons

* **Validate Credentials**: sign in to Spotify (see above).
* **Clear Credentials**: sign out of Spotify on this computer.
* **Spotify Developer Dashboard**: opens Spotify's developer website, for creating your own Client ID.
* **Donate**: opens the page for supporting the add-on's development, after asking you.

## Advanced settings in nvda.ini

A few more settings have no place in the settings panel. They tune how Accessify Play works, and the defaults suit nearly everyone; change one only when you have a reason to, for instance a slow connection.

To change one, exit NVDA, open `nvda.ini` in NVDA's user configuration folder in a text editor, and add a line under `[spotify]` (add that heading at the end of the file if it is not there yet), for example `pollPlayingSeconds = 3`. Save the file and start NVDA again. A value outside the allowed range is ignored, and the default is used instead. Delete the line to go back to the default.

### Checking what is playing

* `pollPlayingSeconds` (default `5`, 1 to 60): how often, in seconds, Accessify Play asks Spotify what is playing while something plays. This is what announces track changes and keeps the lyrics in time.
* `pollPausedSeconds` (default `10`, 1 to 300): the same while playback is paused.
* `pollIdleSeconds` (default `15`, 1 to 600): the same while nothing plays, or Spotify cannot be reached.
* `skipSettleSeconds` (default `0.4`, 0.0 to 5.0): the pause, in seconds, after Next or Previous before Accessify Play asks what plays now.
* `queueSkipStepSeconds` (default `0.2`, 0.0 to 5.0): the pause between steps when you play an item further down the queue.

### Requests to Spotify

* `requestTimeoutSeconds` (default `10`, 1 to 120): how long, in seconds, a request to Spotify may take.
* `requestRetries` (default `3`, 0 to 10): how often a request that failed because of a problem at Spotify is tried again.
* `requestBackoffFactor` (default `0.3`, 0.0 to 10.0): how much longer each of those tries waits than the one before.
* `rateLimitFallbackSeconds` (default `5`, 1 to 3600): how long, in seconds, Accessify Play sends nothing after Spotify limits requests without saying for how long.
* `keepAliveMinSeconds` (default `5`, 1 to 300): the shortest Keep Alive Interval; shorter ones are raised to it.
* `topAndRecentLimit` (default `50`, 1 to 50): how many songs Play My Top Tracks, Play Recently Played, Top Items and Recently Played fetch.
* `artistTopTracksLimit` (default `10`, 1 to 50): how many popular songs the artist window shows. With your own Client ID, Spotify allows at most 10.

### Lyrics

* `lyricsServer` (default `https://lrclib.net/api`): where lyrics come from. Any server with the same API as lrclib.net will do.
* `lyricsTimeoutSeconds` (default `10`, 1 to 120): how long, in seconds, a lyrics request may take.
* `lyricResyncSeconds` (default `10`, 1 to 300): how often, in seconds, the lyrics being read along are put back in time with the song.
* `lyricLateToleranceMs` (default `200`, 0 to 5000): a lyric line is still spoken when it is at most this many milliseconds late.

### Windows and the command layer

* `listLoadDelayMs` (default `300`, 0 to 5000): in the Library, how long, in milliseconds, Accessify Play waits after you stop on a playlist or a Top Items choice before loading it, so arrowing past several sends only one request.
* `layerTimeoutSeconds` (default `30`, 1 to 600): the command layer closes itself after this many seconds without a key.
* `layerBeepHz` (default `440`, 20 to 5000): the pitch, in hertz, of the beep when the command layer opens.
* `layerBeepMs` (default `30`, 0 to 1000): how long that beep lasts, in milliseconds; 0 is silent.
* `layerErrorBeepHz` (default `120`, 20 to 5000): the pitch of the beep for a key the layer does not know.
* `layerErrorBeepMs` (default `120`, 0 to 1000): how long that beep lasts.

## Where Accessify Play keeps its files

Your sign-in, custom command layer keys (`layerConfig.json`, which holds only the keys you chose and whether the layer stays open) and a running sleep timer are stored in the `accessifyPlay` folder inside NVDA's user configuration folder, so they move with a portable copy of NVDA.

---
[Back to Home](readme.html)
