# Masuk dan pengaturan

Semua pengaturan Accessify Play ada di dialog Settings NVDA: buka menu NVDA (`NVDA+N`), lalu Preferences, Settings, dan pilih **Accessify Play**. Dari lapisan perintah, `NVDA+Alt+G` lalu `F4` langsung membukanya.

## Masuk ke Spotify

Tekan **Validate Credentials**. Browser web akan membuka halaman Spotify yang meminta izin agar Accessify Play boleh memakai akun Anda; setujui. Kembali di NVDA, akan terdengar "Validation successful!".

Ini cukup dilakukan sekali. Accessify Play mengingat proses masuk ini, dan Spotify memperbaruinya secara otomatis.

Jika gagal masuk, pastikan Anda sudah menyelesaikan proses masuk di browser dan terhubung ke internet, lalu tekan Validate Credentials lagi.

> Jika Anda memakai Accessify Play sebelum versi 1.9.0: Anda tidak lagi memerlukan aplikasi developer Spotify sendiri, Client ID, maupun callback port. Cukup masuk saja. Memakai Client ID sendiri tetap bisa, tapi tidak wajib; lihat di bawah.

**Clear Credentials** mengeluarkan Anda: tombol ini menghapus data masuk Spotify yang tersimpan di komputer ini, setelah meminta konfirmasi. Gunakan Validate Credentials untuk masuk lagi, misalnya dengan akun lain.

## Memakai Client ID sendiri (opsional)

Secara bawaan, semua orang masuk lewat satu Client ID Spotify yang dipakai bersama, jadi tidak ada yang perlu disiapkan. Spotify membatasi berapa banyak permintaan yang boleh dikirim satu Client ID, dan semua pengguna Client ID bersama berbagi batas itu. Jika Anda sering mendengar "Spotify is limiting requests at the moment", atau Client ID bersama suatu saat tidak bisa dipakai lagi, Anda bisa memakai Client ID sendiri:

1. Tekan **Spotify Developer Dashboard** di pengaturan Accessify Play, lalu masuk dengan akun Spotify Anda.
2. Buat aplikasi (Create app). Nama dan deskripsinya bebas. Di Redirect URIs tambahkan persis `http://127.0.0.1:5588/login`, dan di bagian API yang dipakai pilih **Web API**. Setujui ketentuan Spotify lalu simpan.
3. Buka pengaturan aplikasi itu dan salin **Client ID**-nya, 32 huruf dan angka.
4. Tempelkan ke **Your own Spotify Client ID** di pengaturan Accessify Play, lalu tekan **Validate Credentials** untuk masuk dengannya.

Aplikasi yang Anda buat tunduk pada aturan Spotify sendiri untuk aplikasi developer. Untuk kembali ke Client ID bersama, kosongkan kolomnya lalu tekan OK. Accessify Play menyimpan data masuk terpisah untuk masing-masing, jadi berpindah bolak-balik tidak membuat Anda harus masuk lagi.

## Pengaturan

* **Search Results Limit (1 to 50)**: berapa hasil yang ditampilkan Pencarian sekaligus, bawaannya 20. Setiap daftar panjang lainnya (lagu playlist, episode, bab, tab Pustaka, Browse Categories, dan Featured Playlists) dimuat per halaman dengan ukuran yang sama, dengan item "Load More" di akhir.
* **Seek Duration (seconds, 1 to 60)**: seberapa jauh Seek Forward dan Seek Backward melompat, bawaannya 15 detik.
* **Volume Step (1 to 100)**: seberapa besar Volume Up dan Volume Down mengubah volume, bawaannya 5%.
* **Keep Alive Interval (seconds, 0 = Off, Min = 5)**: seberapa sering Accessify Play menghubungi Spotify di latar belakang, supaya perintah pertama setelah lama diam tetap cepat, paling lama 3600 detik. Bawaannya mati (0), karena setiap pemeriksaan ikut menghabiskan batas permintaan yang dipakai bersama oleh semua pengguna Accessify Play; nyalakan hanya jika perintah pertama setelah jeda terasa lambat. Nilai 1 sampai 4 dinaikkan menjadi 5.
* **Sleep timer starts at (minutes, 1 to 1440)**: jumlah menit yang ditawarkan timer tidur saat dibuka, bawaannya 30.
* **Longest sleep timer (minutes, 1 to 1440)**: jumlah menit terbanyak yang diterima timer tidur, bawaannya 240 (empat jam).
* **Most tracks to queue from an album or playlist (1 to 1000)**: Add to Queue untuk seluruh album atau playlist mengirim satu permintaan per lagu, dan setiap permintaan ikut menghabiskan batas permintaan bersama. Karena itu paling banyak sejumlah ini yang dimasukkan ke antrean, bawaannya 100, dan Accessify Play memberi tahu bila berhenti lebih awal.
* **Play My Top Tracks plays the top tracks of**: periode asal lagu untuk `G` di lapisan perintah: Last 4 Weeks (bawaan), Last 6 Months, atau All Time.
* **Top Items in the Library opens on**: Time Range awal di tab Top Items pada Pustaka, bawaannya Last 6 Months.
* **Search opens on**: Type awal saat jendela Pencarian dibuka, bawaannya Song.
* **Language**: bahasa pesan dan dialog Accessify Play. "Follow NVDA language (default)" mengikuti bahasa NVDA; Anda juga bisa memilih English atau Bahasa Indonesia apa pun bahasa NVDA. Perubahan berlaku setelah NVDA dimulai ulang.
* **Announce track changes automatically**: bila dicentang, NVDA mengumumkan setiap lagu (atau episode) baru saat mulai diputar, dari mana pun lagu itu diputar.
* **New playlists are public**: apakah Public playlist sudah dicentang saat Anda membuat playlist. Bawaannya dicentang.
* **Your own Spotify Client ID (optional, leave blank to use the shared one)**: lihat "Memakai Client ID sendiri" di atas.

## Tombol

* **Validate Credentials**: masuk ke Spotify (lihat di atas).
* **Clear Credentials**: keluar dari Spotify di komputer ini.
* **Spotify Developer Dashboard**: membuka situs developer Spotify, untuk membuat Client ID sendiri.
* **Donate**: membuka halaman untuk mendukung pengembangan add-on, setelah bertanya kepada Anda.
* **Window Shortcuts...**: mengubah pintasan di dalam jendela Accessify Play, seperti `Alt+P` untuk memutar; lihat [Mengubah perintah dan pintasan](customizing_commands.html).

## Pengaturan lanjutan di nvda.ini

Beberapa pengaturan lain tidak ada di panel pengaturan. Pengaturan ini menyetel cara kerja Accessify Play, dan nilai bawaannya cocok untuk hampir semua orang; ubah hanya bila ada alasannya, misalnya koneksi yang lambat.

Untuk mengubahnya, keluar dari NVDA, buka `nvda.ini` di folder konfigurasi pengguna NVDA dengan editor teks, lalu tambahkan baris di bawah `[spotify]` (tambahkan judul itu di akhir berkas bila belum ada), misalnya `pollPlayingSeconds = 3`. Simpan berkasnya lalu jalankan NVDA lagi. Nilai di luar rentang yang diizinkan diabaikan, dan nilai bawaan dipakai sebagai gantinya. Hapus barisnya untuk kembali ke nilai bawaan.

### Memeriksa apa yang sedang diputar

* `pollPlayingSeconds` (bawaan `5`, 1 sampai 60): seberapa sering, dalam detik, Accessify Play menanyakan ke Spotify apa yang sedang diputar selama ada yang diputar. Inilah yang mengumumkan pergantian lagu dan menjaga lirik tetap selaras.
* `pollPausedSeconds` (bawaan `10`, 1 sampai 300): sama, selama pemutaran dijeda.
* `pollIdleSeconds` (bawaan `15`, 1 sampai 600): sama, selama tidak ada yang diputar atau Spotify tidak dapat dihubungi.
* `skipSettleSeconds` (bawaan `0.4`, 0.0 sampai 5.0): jeda, dalam detik, setelah Next atau Previous sebelum Accessify Play menanyakan apa yang sekarang diputar.
* `queueSkipStepSeconds` (bawaan `0.2`, 0.0 sampai 5.0): jeda di antara langkah saat Anda memutar item yang lebih jauh di antrean.

### Permintaan ke Spotify

* `requestTimeoutSeconds` (bawaan `10`, 1 sampai 120): berapa lama, dalam detik, satu permintaan ke Spotify boleh berlangsung.
* `requestRetries` (bawaan `3`, 0 sampai 10): berapa kali permintaan yang gagal karena masalah di Spotify dicoba lagi.
* `requestBackoffFactor` (bawaan `0.3`, 0.0 sampai 10.0): seberapa lebih lama setiap percobaan menunggu dibanding sebelumnya.
* `rateLimitFallbackSeconds` (bawaan `5`, 1 sampai 3600): berapa lama, dalam detik, Accessify Play tidak mengirim apa pun setelah Spotify membatasi permintaan tanpa menyebutkan lamanya.
* `keepAliveMinSeconds` (bawaan `5`, 1 sampai 300): Keep Alive Interval terpendek; nilai yang lebih pendek dinaikkan ke sini.
* `topAndRecentLimit` (bawaan `50`, 1 sampai 50): berapa lagu yang diambil oleh Play My Top Tracks, Play Recently Played, Top Items, dan Recently Played.
* `artistTopTracksLimit` (bawaan `10`, 1 sampai 50): berapa lagu populer yang ditampilkan jendela artis. Dengan Client ID sendiri, Spotify mengizinkan paling banyak 10.

### Lirik

* `lyricsServer` (bawaan `https://lrclib.net/api`): asal lirik. Server apa pun dengan API yang sama seperti lrclib.net bisa dipakai.
* `lyricsTimeoutSeconds` (bawaan `10`, 1 sampai 120): berapa lama, dalam detik, satu permintaan lirik boleh berlangsung.
* `lyricResyncSeconds` (bawaan `10`, 1 sampai 300): seberapa sering, dalam detik, lirik yang dibacakan diselaraskan lagi dengan lagunya.
* `lyricLateToleranceMs` (bawaan `200`, 0 sampai 5000): satu baris lirik tetap dibacakan bila terlambat paling lama sekian milidetik.

### Jendela dan lapisan perintah

* `listLoadDelayMs` (bawaan `300`, 0 sampai 5000): di Pustaka, berapa lama, dalam milidetik, Accessify Play menunggu setelah Anda berhenti di sebuah playlist atau pilihan Top Items sebelum memuatnya, sehingga melewati beberapa pilihan dengan panah hanya mengirim satu permintaan.
* `layerTimeoutSeconds` (bawaan `30`, 1 sampai 600): lapisan perintah menutup sendiri setelah sekian detik tanpa tombol.
* `layerBeepHz` (bawaan `440`, 20 sampai 5000): nada, dalam hertz, bunyi bip saat lapisan perintah dibuka.
* `layerBeepMs` (bawaan `30`, 0 sampai 1000): lamanya bunyi bip itu, dalam milidetik; 0 berarti tanpa bunyi.
* `layerErrorBeepHz` (bawaan `120`, 20 sampai 5000): nada bunyi bip untuk tombol yang tidak dikenal lapisan.
* `layerErrorBeepMs` (bawaan `120`, 0 sampai 1000): lamanya bunyi bip itu.

## Tempat Accessify Play menyimpan berkasnya

Data masuk, tombol lapisan perintah yang Anda ubah (`layerConfig.json`, yang hanya menyimpan tombol pilihan Anda dan apakah lapisan tetap terbuka), dan timer tidur yang sedang berjalan disimpan di folder `accessifyPlay` di dalam folder konfigurasi pengguna NVDA, sehingga ikut berpindah bersama NVDA portabel.

---
[Kembali ke Beranda](readme.html)
