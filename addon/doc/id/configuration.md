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

* **Search Results Limit (1 to 50)**: berapa hasil yang ditampilkan Pencarian sekaligus, bawaannya 20. Daftar episode, bab, dan lagu playlist dimuat per halaman dengan ukuran yang sama, dengan item "Load More" di akhir.
* **Seek Duration (seconds, 1 to 60)**: seberapa jauh Seek Forward dan Seek Backward melompat, bawaannya 15 detik.
* **Volume Step (1 to 100)**: seberapa besar Volume Up dan Volume Down mengubah volume, bawaannya 5%.
* **Keep Alive Interval (seconds, 0 = Off, Min = 5)**: seberapa sering Accessify Play menghubungi Spotify di latar belakang, supaya perintah pertama setelah lama diam tetap cepat. Bawaannya mati (0), karena setiap pemeriksaan ikut menghabiskan batas permintaan yang dipakai bersama oleh semua pengguna Accessify Play; nyalakan hanya jika perintah pertama setelah jeda terasa lambat. Nilai 1 sampai 4 dinaikkan menjadi 5.
* **Language**: bahasa pesan dan dialog Accessify Play. "Follow NVDA language (default)" mengikuti bahasa NVDA; Anda juga bisa memilih English atau Bahasa Indonesia apa pun bahasa NVDA. Perubahan berlaku setelah NVDA dimulai ulang.
* **Announce track changes automatically**: bila dicentang, NVDA mengumumkan setiap lagu (atau episode) baru saat mulai diputar, dari mana pun lagu itu diputar.
* **Your own Spotify Client ID (optional, leave blank to use the shared one)**: lihat "Memakai Client ID sendiri" di atas.

## Tombol

* **Validate Credentials**: masuk ke Spotify (lihat di atas).
* **Clear Credentials**: keluar dari Spotify di komputer ini.
* **Spotify Developer Dashboard**: membuka situs developer Spotify, untuk membuat Client ID sendiri.
* **Donate**: membuka halaman untuk mendukung pengembangan add-on, setelah bertanya kepada Anda.

## Tempat Accessify Play menyimpan berkasnya

Data masuk, tombol lapisan perintah yang Anda ubah, dan timer tidur yang sedang berjalan disimpan di folder `accessifyPlay` di dalam folder konfigurasi pengguna NVDA, sehingga ikut berpindah bersama NVDA portabel.

---
[Kembali ke Beranda](readme.html)
