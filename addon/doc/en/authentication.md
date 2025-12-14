# Authentication & Migration Update (Version 1.3.0)

With version 1.3.0, Accessify Play has undergone a significant update to its authentication system to enhance security and improve user experience, especially for portable NVDA installations.

*   **Enhanced Security with PKCE:** The addon now utilizes the Proof Key for Code Exchange (PKCE) authentication flow. This modern and more secure method eliminates the need for a `Client Secret`, making your Spotify integration safer.
*   **Portable Client ID Storage:** Your Spotify Client ID is no longer stored within NVDA's configuration files. Instead, it is now saved in a dedicated, portable file located at `%userprofile%/.spotify_client_id.json`. This ensures your Client ID remains intact even if you move or reinstall NVDA, and it's easier to manage.
*   **Simplified Settings:** The 'Client Secret' field has been removed from the Accessify Play settings panel, streamlining the setup process. The 'Client ID' input is now managed via a dynamic button that allows you to easily add, view, or edit your Client ID.
*   **Seamless Migration:** If you are upgrading from an older version of Accessify Play and have your Client ID (or Client Secret) still stored in NVDA's configuration, a new **"Migrate Old Credentials"** button will appear in the Accessify Play settings panel. Clicking this button will automatically:
    1.  Move your existing Client ID to the new portable `%userprofile%/.spotify_client_id.json` file.
    2.  Remove both the old Client ID and the obsolete Client Secret from NVDA's configuration.
    This ensures a smooth transition to the new, more secure system.

---

# 🤔 Why This Authentication Method? (Instead of a Simple Login Button)

You might be wondering why Accessify Play requires you to create your own Spotify application and input a Client ID, instead of offering a simple "Login to Spotify" button like many other apps (e.g., Alexa, Google Home, etc.). The answer lies in Spotify's API policies and the challenges faced by independent developers.

To provide a seamless "Login to Spotify" experience without requiring users to become "mini-developers," an application needs to apply for and be granted an **Extended Quota** from Spotify. The requirements for obtaining such an extended quota are quite extraordinary and often include:

*   **Significant User Base:** Demonstrating a large and active user base.
*   **Business Model:** A clear and sustainable business model.
*   **Legal & Security Reviews:** Extensive legal and security reviews by Spotify.
*   **Brand Alignment:** Strong alignment with Spotify's brand and strategic goals.

For a small, independent, and open-source accessibility addon like Accessify Play, meeting these stringent requirements is **almost impossible**. The resources, legal overhead, and user base needed are far beyond what this project can realistically achieve.

Therefore, the current method, while requiring a few extra steps from the user, is a necessary workaround. It allows Accessify Play to function and provide its valuable accessibility features by leveraging Spotify's standard developer access, without needing to meet the prohibitive criteria for extended quotas. This approach empowers you, the user, to directly control your Spotify API access, ensuring the addon remains functional and accessible.


---
[Back to Home](README.html)