# Configuration Guide

To use this addon, you need to get a **Client ID** and **Client Secret** from the Spotify Developer Dashboard. Follow these steps carefully.

## Step 1: Create a Spotify App

1.  Open the Accessify Play settings in NVDA (NVDA menu -> Preferences -> Settings -> Accessify Play).
2.  Click the **"Go to Developer Dashboard"** button. This will open the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) in your web browser. Log in if prompted.
3.  Click the "Create app" button.
4.  Fill out the form:
    * **App name:** Give it a name (e.g., "NVDA Controller").
    * **App description:** A short description is fine.
    * **Redirect URI:** **This is the most important step.** The addon listens on your local machine for the authentication callback. You must enter this URI exactly: `http://127.0.0.1:8539/callback`
5.  You may be asked which API to use. **Please select "Web API"**.
6.  Agree to the terms and click "Save".

## Step 2: Get Your Credentials

1.  On your new app's dashboard, click "Settings".
2.  You will see your **Client ID**.
3.  Copy this long string of text.

## Step 3: Configure the Addon in NVDA

1.  Open the NVDA menu (`NVDA+N`), go to Preferences, then Settings.
2.  In the categories list, select "Accessify Play".
3.  Locate the **"Add Client ID"** (or "Display/Edit Client ID") button. Click it to open a dialog where you can paste your **Client ID**.
4.  Review the other settings:
    * **Callback Port:** Only change this if you have a port conflict and you have also changed it in the Spotify Dashboard. *(See note in Step 1)*.
    * **Announce track changes automatically:** Check this box if you want NVDA to announce every new song as it begins playing.
5.  Press the **"Validate Credentials"** button. Your web browser will open and ask you to grant permissions. Click "Agree".
6.  If successful, you will see a "Validation successful!" message. If not, carefully re-check all steps, especially the Redirect URI and your Client ID.
7.  Click "OK" to save and close the settings. The addon is now ready to use!


---
[Back to Home](README.html)