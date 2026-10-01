# Lyrics

Lyrics come from [lrclib.net](https://lrclib.net), a free, community-run database whose lyrics are in the public domain. Most popular songs have *synced* lyrics, with a time for every line; some have plain text only, and some have none.

## Lyrics window (`W`)

`NVDA+Alt+G` then `W` opens the lyrics of the song that is playing. Read them line by line with the arrow keys.

* `Enter` on a line jumps the song to that line (synced lyrics only).
* **Jump to Current** (`Alt+J`) moves to the line being sung now (synced lyrics only).
* **Copy Lyrics** (`Alt+L`) copies the lyrics as text.
* **Copy with Timestamps** (`Alt+T`) copies synced lyrics with their times, in LRC format.
* **Close** or `Escape` closes the window.

The window follows the music: when the next song starts, it shows the new song's lyrics. If a song has no lyrics, the window says so.

## Automatic lyric reading (`Y`)

`NVDA+Alt+G` then `Y` makes NVDA speak each line as it is sung, in time with the music. Press it again to stop. This needs synced lyrics; if a song has none, you are told.

It pauses when you pause the music, catches up within a few seconds when you seek, and carries on with the next song by itself. If the lyrics window is open, its cursor follows the line being read.

## Lyrics for any song, without playing it

In Search, select a song and press `Alt+W`. In any list of songs (search results, albums, playlists, artist discographies and the Library), choose **Show Lyrics** in the context menu.

The lyrics open in the same window, as a preview: `Enter` doesn't jump and there is no Jump to Current, since the song isn't the one playing, and the window stays on that song when the music changes. If the song has no lyrics, you are told and no window opens.

---
[Back to Home](readme.html)
