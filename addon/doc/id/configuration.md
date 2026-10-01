# Masuk dan pengaturan

Semua pengaturan Accessify Play ada di dialog Settings NVDA: buka menu NVDA (`NVDA+N`), lalu Preferences, Settings, dan pilih **Accessify Play**. Dari lapisan perintah, `NVDA+Alt+G` lalu `F4` langsung membukanya.

## Masuk ke Spotify

Tekan **Validate Credentials**. Browser web akan membuka halaman Spotify yang meminta izin agar Accessify Play boleh memakai akun Anda; setujui. Kembali di NVDA, akan terdengar "Validation successful!".

Ini cukup dilakukan sekali. Accessify Play mengingat proses masuk ini, dan Spotify memperbaruinya secara otomatis.

Jika gagal masuk, pastikan Anda sudah menyelesaikan proses masuk di browser dan terhubung ke internet, lalu tekan Validate Credentials lagi.

> Jika Anda memakai Accessify Play sebelum versi 1.9.0: Anda tidak lagi memerlukan aplikasi developer Spotify sendiri, Client ID, maupun callback port. Cukup masuk saja.

**Clear Credentials** mengeluarkan Anda: tombol ini menghapus data masuk Spotify yang tersimpan di komputer ini, setelah meminta konfirmasi. Gunakan Validate Credentials untuk masuk lagi, misalnya dengan akun lain.

## Pengaturan

* **Search Results Limit (1 to 50)**: berapa hasil yang ditampilkan Pencarian sekaligus, bawaannya 20. Daftar episode, bab, dan lagu playlist dimuat per halaman dengan ukuran yang sama, dengan item "Load More" di akhir.
* **Seek Duration (seconds, 1 to 60)**: seberapa jauh Seek Forward dan Seek Backward melompat, bawaannya 15 detik.
* **Volume Step (1 to 100)**: seberapa besar Volume Up dan Volume Down mengubah volume, bawaannya 5%.
* **Keep Alive Interval (seconds, 0 = Off, Min = 5)**: seberapa sering Accessify Play menghubungi Spotify di latar belakang, supaya perintah pertama setelah lama diam tetap cepat. Bawaannya 30 detik; 0 mematikannya. Nilai 1 sampai 4 dinaikkan menjadi 5.
* **Language**: bahasa pesan dan dialog Accessify Play. "Follow NVDA language (default)" mengikuti bahasa NVDA; Anda juga bisa memilih English atau Bahasa Indonesia apa pun bahasa NVDA. Perubahan berlaku setelah NVDA dimulai ulang.
* **Announce track changes automatically**: bila dicentang, NVDA mengumumkan setiap lagu (atau episode) baru saat mulai diputar, dari mana pun lagu itu diputar.

## Tombol

* **Validate Credentials**: masuk ke Spotify (lihat di atas).
* **Clear Credentials**: keluar dari Spotify di komputer ini.
* **Donate**: membuka halaman untuk mendukung pengembangan add-on, setelah bertanya kepada Anda.

## Tempat Accessify Play menyimpan berkasnya

Data masuk, tombol lapisan perintah yang Anda ubah, dan timer tidur yang sedang berjalan disimpan di folder `accessifyPlay` di dalam folder konfigurasi pengguna NVDA, sehingga ikut berpindah bersama NVDA portabel.

---
[Kembali ke Beranda](readme.html)
