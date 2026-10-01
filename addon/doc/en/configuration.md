# Sign-in and settings

All of Accessify Play's settings are in NVDA's Settings dialog: open the NVDA menu (`NVDA+N`), then Preferences, Settings, and choose **Accessify Play**. From the command layer, `NVDA+Alt+G` then `F4` opens it directly.

## Signing in to Spotify

Press **Validate Credentials**. Your web browser opens a Spotify page asking you to allow Accessify Play to use your account; agree to it. Back in NVDA you will hear "Validation successful!".

You only need to do this once. Accessify Play remembers the sign-in, and Spotify renews it automatically.

If signing in fails, make sure you finished signing in in the browser and that you are connected to the internet, then press Validate Credentials again.

> If you have used Accessify Play before version 1.9.0: you no longer need your own Spotify developer app, Client ID or callback port. Signing in is all it takes.

**Clear Credentials** signs you out: it deletes the stored Spotify sign-in from this computer, after asking you to confirm. Use Validate Credentials to sign in again, for example with a different account.

## Settings

* **Search Results Limit (1 to 50)**: how many results Search shows at a time, 20 by default. Lists of episodes, chapters and playlist tracks load in pages of the same size, with a "Load More" item at the end.
* **Seek Duration (seconds, 1 to 60)**: how far Seek Forward and Seek Backward jump, 15 seconds by default.
* **Volume Step (1 to 100)**: how much Volume Up and Volume Down change the volume, 5% by default.
* **Keep Alive Interval (seconds, 0 = Off, Min = 5)**: how often Accessify Play checks in with Spotify in the background, so the first command after a quiet period responds quickly. 30 seconds by default; 0 turns it off. Values from 1 to 4 are raised to 5.
* **Language**: the language of Accessify Play's messages and dialogs. "Follow NVDA language (default)" uses NVDA's language; you can also choose English or Bahasa Indonesia regardless of NVDA's language. A change takes effect after restarting NVDA.
* **Announce track changes automatically**: when checked, NVDA announces each new track (or episode) as it starts, wherever it was started from.

## Buttons

* **Validate Credentials**: sign in to Spotify (see above).
* **Clear Credentials**: sign out of Spotify on this computer.
* **Donate**: opens the page for supporting the add-on's development, after asking you.

## Where Accessify Play keeps its files

Your sign-in, custom command layer keys and a running sleep timer are stored in the `accessifyPlay` folder inside NVDA's user configuration folder, so they move with a portable copy of NVDA.

---
[Back to Home](readme.html)
