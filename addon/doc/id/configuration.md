# Panduan Konfigurasi

Untuk menggunakan add-on ini, Anda perlu mendapatkan **Client ID** dan **Client Secret** dari Dasbor Pengembang Spotify. Ikuti langkah-langkah ini dengan cermat.

## Langkah 1: Buat Aplikasi Spotify

1.  Buka pengaturan Accessify Play di NVDA (Menu NVDA -> Preferensi -> Pengaturan -> Accessify Play).
2.  Klik tombol **"Buka Dasbor Pengembang"**. Ini akan membuka [Dasbor Pengembang Spotify](https://developer.spotify.com/dashboard) di browser web Anda. Masuk jika diminta.
3.  Klik tombol "Create app".
4.  Isi formulir:
    *   **Nama aplikasi:** Beri nama (mis., "NVDA Controller").
    *   **Deskripsi aplikasi:** Deskripsi singkat sudah cukup.
    *   **Redirect URI:** Ini adalah langkah yang paling penting. Add-on mendengarkan di mesin lokal Anda untuk callback otentikasi. Anda harus memasukkan URI ini dengan tepat: `http://127.0.0.1:8539/callback`
5.  Anda mungkin akan ditanya API mana yang akan digunakan. **Silakan pilih "Web API"**.
6.  Setujui persyaratannya dan klik "Save".

## Langkah 2: Dapatkan Kredensial Anda

1.  Di dasbor aplikasi baru Anda, klik "Settings".
2.  Anda akan melihat **Client ID** Anda.
3.  Salin teks panjang ini.

## Langkah 3: Konfigurasi Add-on di NVDA

1.  Buka menu NVDA (`NVDA+N`), pergi ke Preferensi, lalu Pengaturan.
2.  Dalam daftar kategori, pilih "Accessify Play".
3.  Temukan tombol **"Tambah Client ID"** (atau "Tampilkan/Edit Client ID"). Klik untuk membuka dialog di mana Anda dapat menempelkan **Client ID** Anda.
4.  Tinjau pengaturan lainnya:
    *   **Port Callback:** Hanya ubah ini jika Anda memiliki konflik port dan Anda juga telah mengubahnya di Dasbor Spotify.
    *   **Umumkan pergantian lagu secara otomatis:** Centang kotak ini jika Anda ingin NVDA mengumumkan setiap lagu baru saat mulai diputar.
5.  Tekan tombol **"Validasi Kredensial"**. Browser web Anda akan terbuka dan meminta Anda untuk memberikan izin. Klik "Agree".
6.  Jika berhasil, Anda akan melihat pesan "Validasi berhasil!". Jika tidak, periksa kembali semua langkah dengan cermat, terutama Redirect URI dan Client ID Anda.
7.  Klik "OK" untuk menyimpan dan menutup pengaturan. Add-on sekarang siap digunakan!


---
[Kembali ke Beranda](README.html)