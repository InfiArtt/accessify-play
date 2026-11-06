# Queue

`NVDA+Alt+G` then `Q` opens the queue. The first item is the one playing ("Playing"), followed by what comes next ("Queue").

Each row reads like a song or episode anywhere else, such as "Queue: Yesterday - The Beatles (2:05)".

* `Enter` (or `Alt+P`) on an item skips ahead to it.
* `Alt+L` copies the item's Spotify link, and `Alt+W` shows a song's lyrics.
* **Refresh** (`Alt+R`) reloads the list.
* The context menu is the item's usual one (see [Lists and context menus](lists_guide.html)), so you can save a song, add it to a playlist or go to its album from here. Its Play skips ahead to the item.

These are the default keys; see [Customizing commands and shortcuts](customizing_commands.html) to change them.

`NVDA+Alt+G` then `E` announces only the next item, without opening the window.

To add to the queue, use Add to Queue (`Alt+Q`) in Search, the Library or any track list. For a whole album or playlist, Accessify Play queues the tracks one by one, at most 100 of them (see **Most tracks to queue from an album or playlist** in the settings), and says so when it stops early.

## Why the queue sometimes doesn't match the Spotify app

Accessify Play shows the queue exactly as Spotify reports it, and Spotify reports it reliably only in some situations:

* **Accurate:** songs you added with Add to Queue, and the rest of an album or playlist playing in order with shuffle off.
* **Not accurate with shuffle on:** Spotify reports the playlist in its saved order, not the shuffled order the app will actually play.
* **Not accurate once autoplay starts:** when an album or playlist ends and Spotify continues with similar songs, it doesn't say in advance which songs those will be.

That is why the window reminds you that upcoming tracks may change. Use Refresh to see the latest list.

---
[Back to Home](readme.html)
