# Customizing the command layer

You can change which key runs each command in the layer, and whether the layer stays open afterwards.

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

When you close the editor after making changes, the new keys work right away. Accessify Play also offers to restart NVDA, which you can decline.

`F1`, `F2` and `Escape` always keep their meaning in the layer and can't be reassigned.

## A shortcut without the layer

To run a command with a single gesture, without pressing `NVDA+Alt+G` first, assign it in NVDA's Input Gestures dialog (NVDA menu, Preferences, Input Gestures), under **Accessify Play**. You can change `NVDA+Alt+G` itself there too ("Accessify Play layer commands").

---
[Back to Command keys](keybindings.html)
