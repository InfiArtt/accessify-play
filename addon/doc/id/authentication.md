# Pembaruan Otentikasi & Migrasi (Versi 1.3.0)

Dengan versi 1.3.0, Accessify Play telah mengalami pembaruan signifikan pada sistem otentikasinya untuk meningkatkan keamanan dan pengalaman pengguna, terutama untuk instalasi NVDA portabel.

*   **Keamanan yang Ditingkatkan dengan PKCE:** Add-on sekarang menggunakan alur otentikasi Proof Key for Code Exchange (PKCE). Metode modern dan lebih aman ini menghilangkan kebutuhan akan `Client Secret`, membuat integrasi Spotify Anda lebih aman.
*   **Penyimpanan Client ID Portabel:** Client ID Spotify Anda tidak lagi disimpan dalam file konfigurasi NVDA. Sebaliknya, sekarang disimpan dalam file khusus portabel yang berlokasi di `%userprofile%/.spotify_client_id.json`. Ini memastikan Client ID Anda tetap utuh bahkan jika Anda memindahkan atau menginstal ulang NVDA, dan lebih mudah untuk dikelola.
*   **Pengaturan yang Disederhanakan:** Bidang 'Client Secret' telah dihapus dari panel pengaturan Accessify Play, menyederhanakan proses penyiapan. Input 'Client ID' sekarang dikelola melalui tombol dinamis yang memungkinkan Anda dengan mudah menambah, melihat, atau mengedit Client ID Anda.
*   **Migrasi yang Mulus:** Jika Anda meningkatkan dari versi Accessify Play yang lebih lama dan Client ID (atau Client Secret) Anda masih tersimpan di konfigurasi NVDA, tombol baru **"Migrasikan Kredensial Lama"** akan muncul di panel pengaturan Accessify Play. Mengklik tombol ini akan secara otomatis:
    1.  Memindahkan Client ID Anda yang ada ke file portabel baru `%userprofile%/.spotify_client_id.json`.
    2.  Menghapus Client ID lama dan Client Secret yang sudah usang dari konfigurasi NVDA.Ini memastikan transisi yang mulus ke sistem baru yang lebih aman.

---

# 🤔 Mengapa Metode Otentikasi Ini? (Bukan Tombol Login Sederhana)

Anda mungkin bertanya-tanya mengapa Accessify Play mengharuskan Anda untuk membuat aplikasi Spotify Anda sendiri dan memasukkan Client ID, alih-alih menawarkan tombol "Masuk ke Spotify" yang sederhana seperti banyak aplikasi lain (mis., Alexa, Google Home, dll.). Jawabannya terletak pada kebijakan API Spotify dan tantangan yang dihadapi oleh pengembang independen.

Untuk menyediakan pengalaman "Masuk ke Spotify" yang mulus tanpa mengharuskan pengguna menjadi "pengembang-mini," sebuah aplikasi perlu mengajukan dan diberikan **Extended Quota** dari Spotify. Persyaratan untuk mendapatkan kuota yang diperpanjang semacam itu sangat luar biasa dan sering kali mencakup:

*   **Basis Pengguna yang Signifikan:** Menunjukkan basis pengguna yang besar dan aktif.
*   **Model Bisnis:** Model bisnis yang jelas dan berkelanjutan.
*   **Tinjauan Hukum & Keamanan:** Tinjauan hukum dan keamanan yang ekstensif oleh Spotify.
*   **Kesesuaian Merek:** Keselarasan yang kuat dengan merek dan tujuan strategis Spotify.

Untuk sebuah add-on aksesibilitas yang kecil, independen, dan sumber terbuka seperti Accessify Play, memenuhi persyaratan ketat ini **hampir mustahil**. Sumber daya, biaya hukum, dan basis pengguna yang dibutuhkan jauh melampaui apa yang dapat dicapai secara realistis oleh proyek ini.

Oleh karena itu, metode saat ini, meskipun memerlukan beberapa langkah tambahan dari pengguna, adalah solusi yang diperlukan. Ini memungkinkan Accessify Play untuk berfungsi dan menyediakan fitur aksesibilitasnya yang berharga dengan memanfaatkan akses pengembang standar Spotify, tanpa perlu memenuhi kriteria yang memberatkan untuk kuota yang diperpanjang. Pendekatan ini memberdayakan Anda, sebagai pengguna, untuk mengontrol langsung akses API Spotify Anda, memastikan add-on tetap fungsional dan dapat diakses.


---
[Kembali ke Beranda](README.html)