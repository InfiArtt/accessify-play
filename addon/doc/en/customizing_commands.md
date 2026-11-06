# Customizing commands and shortcuts

You can change which key runs each command in the layer, and whether the layer stays open afterwards; and the shortcuts inside Accessify Play's windows.

## Opening the editor

Press `NVDA+Alt+G`, then `F2`. The **Command Layer Editor** lists every command with four columns:

* **Command**: the command's name, for example Play/Pause.
* **Shortcut**: the key that runs it inside the layer.
* **Keep Open**: whether the layer stays open after the command runs.
* **Description**: what the command does.

## Changing a command

1. Select the command and press `Enter`, or the **Edit** button.
2. In **Shortcut**, type the key to use, for example `p` or `shift+d`. Type special keys by name: `space`, `leftArrow`, `pageUp`, `end`, `f12` and so on. Leave it empty to remove the command from the layer.
3. Check **Keep layer open after executing** if you want to be able to press the command again straight away, as for volume or skipping tracks.
4. Press OK.

**Reset to Defaults** puts every command back to its original key and Keep Open setting, after asking you.

When you close the editor after making changes, the new keys work right away; there is no need to restart NVDA.

`F1`, `F2` and `Escape` always keep their meaning in the layer and can't be reassigned. A key can run only one command: if you choose a key that another command already uses, the editor says which command that is and lets you choose another key.

## A shortcut without the layer

To run a command with a single gesture, without pressing `NVDA+Alt+G` first, assign it in NVDA's Input Gestures dialog (NVDA menu, Preferences, Input Gestures), under **Accessify Play**. You can change `NVDA+Alt+G` itself there too ("Accessify Play layer commands").

## Shortcuts in the windows

The shortcuts inside Accessify Play's windows, such as `Alt+P` to play the selected item, can be changed too. Open the NVDA menu, then Preferences, Settings, choose the **Accessify Play** category and press **Window Shortcuts...**. The list shows each action with its keys:

1. Select an action and press `Enter`, or **Change...**.
2. Type the keys the way NVDA writes them, for example `alt+p`, `ctrl+shift+tab` or `f5`. Type special keys by name: `tab`, `enter`, `space`, `backspace`, `delete`, `insert`, `home`, `end`, `pageUp`, `pageDown`, `upArrow`, `downArrow`, `leftArrow`, `rightArrow`, `f1` to `f24`. Give several keys by separating them with a space, or leave the field empty for no shortcut.
3. Press OK, then OK in the Window Shortcuts dialog and in NVDA's settings to save. Windows you open from then on use the new keys.

A few rules keep the keys from getting in each other's way:

* A shortcut that works anywhere in a window needs `Alt` or `Ctrl`, or must be a function key, so it does not get in the way of typing in a search field.
* The keys for moving and removing tracks in the Library work only in its track list, so they may be any key, such as `delete`.
* For going to a search type or tab by number, type only the keys to hold with the number, such as `ctrl` (for `Ctrl+1`, `Ctrl+2` and so on) or `alt+shift`.
* A key can belong to only one action. If you choose a key another action already has, you are told which one.
* The underlined letters of buttons (such as `Alt+C` for Close) are not settings. Avoid choosing them for a shortcut, as the shortcut would win.

**Reset to Defaults** puts every shortcut back, after asking you.

The shortcuts are settings in `nvda.ini` too, under `[spotify]`, should you prefer to edit them there. Keys that cannot be a shortcut are ignored, and the default is used instead.

* `keyPlay` (default `alt+p`): play the selected item, in every window with a list.
* `keyQueue` (default `alt+q`): add the selected item to the queue.
* `keyCopyLink` (default `alt+l`): copy the selected item's Spotify link.
* `keyLyrics` (default `alt+w`): show the lyrics of the selected song: in Search, albums, playlists, the artist window and the Library.
* `keyRefresh` (default `alt+r`): load the list again, in the Library and the queue.
* `keyFollow` (default `alt+f`): in Search, follow or unfollow the selected artist.
* `keyDiscography` (default `alt+d`): in Search, open the selected artist's discography.
* `keySearchField` (default `ctrl+f`): in Search, go back to the search field.
* `keyNextTab` (default `ctrl+tab ctrl+pageDown`): the next search type, or the next tab of the artist window.
* `keyPreviousTab` (default `ctrl+shift+tab ctrl+pageUp`): the previous search type or tab.
* `keyTabNumber` (default `ctrl`): held with a number, go to that search type or tab.
* `keySaveEpisode` (default `alt+s`): in a show's episodes, save or unsave the selected episode.
* `keyNewPlaylist` (default `ctrl+n`): in the Library, create a playlist.
* `keyMoveTrackUp` (default `alt+upArrow`) and `keyMoveTrackDown` (default `alt+downArrow`): in the Library, move a track of your own playlist.
* `keyRemoveTrack` (default `delete`): in the Library, remove a track from your own playlist.

---
[Back to Command keys](keybindings.html)
