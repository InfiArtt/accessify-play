# donate.py
import webbrowser
import wx
from gui import messageBox


def open_donate_link():
    """
    Opens the PayPal donation link in the default web browser.
    """
    try:
        # Translators: The message shown when the user clicks the donate button.
        if (
            messageBox(
                _(
                    "Thank you for considering a donation! This will open a link in your web browser."
                ),
                _("Donate"),
                wx.OK | wx.CANCEL | wx.ICON_INFORMATION,
            )
            == wx.OK
        ):
            webbrowser.open("https://www.paypal.com/paypalme/rafli23115")
    except Exception as e:
        # Fallback message if the browser fails to open
        wx.CallAfter(
            messageBox,
            f"Could not open donation link. Please visit the addon's page for details.\nError: {e}",
            "Error",
        )
