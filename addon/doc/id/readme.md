# Accessify Play

Accessify Play memungkinkan Anda mengendalikan Spotify dari NVDA: pemutaran, pencarian, pustaka, playlist, podcast, buku audio, dan lirik. Semuanya bekerja di perangkat Spotify Connect mana pun yang sedang memutar (komputer ini, ponsel, speaker pintar, atau konsol), tanpa perlu berpindah ke aplikasi Spotify.

> **Wajib Spotify Premium.** Spotify hanya mengizinkan akun Premium mengendalikan pemutaran lewat API-nya, jadi sebagian besar perintah tidak akan berfungsi dengan akun gratis.

> Nama tombol, menu, dan tab di panduan ini ditulis seperti pada versi bahasa Inggris. Jika Accessify Play memakai bahasa Indonesia, sebagian di antaranya sudah diterjemahkan.

## Persyaratan

* NVDA 2025.1 atau lebih baru.
* Akun Spotify Premium.
* Aplikasi Spotify (atau perangkat Spotify Connect lain) yang terbuka dan sudah masuk, supaya ada yang bisa dikendalikan.

## Memulai

1. Buka menu NVDA (`NVDA+N`), lalu Preferences, Settings, dan pilih kategori **Accessify Play**.
2. Tekan **Validate Credentials**. Browser web akan membuka halaman Spotify yang meminta izin agar Accessify Play boleh memakai akun Anda. Setujui.
3. Setelah terdengar "Validation successful!", tekan OK. Selesai: tidak perlu membuat aplikasi developer Spotify, Client ID, atau mengatur port.

Selengkapnya: [Masuk dan pengaturan](configuration.html).

## Cara memakainya: lapisan perintah

Accessify Play hanya punya satu pintasan bawaan: **`NVDA+Alt+G`**. Pintasan ini membuka *lapisan perintah* (command layer). Tekan satu tombol lagi dan perintah yang sesuai dijalankan. Contohnya, `NVDA+Alt+G` lalu `P` untuk memutar atau menjeda, dan `NVDA+Alt+G` lalu `S` untuk membuka Pencarian. Di dalam lapisan, `F1` menampilkan semua tombol dan `Escape` menutup lapisan.

Anda bisa mengubah tombol-tombol di lapisan, dan juga memberi perintah mana pun pintasannya sendiri lewat dialog Input Gestures NVDA, di bawah "Accessify Play".

* [Tombol perintah](keybindings.html): semua tombol di lapisan.
* [Mengubah tombol lapisan perintah](customizing_commands.html).

## Panduan

* [Pencarian](search_guide.html): lagu, album, artis, playlist, podcast, dan buku audio; Browse Categories dan Featured Playlists.
* [Pustaka](library_management.html): playlist Anda, musik, podcast, dan buku audio yang disimpan, artis yang diikuti, item teratas, dan yang baru diputar.
* [Lirik](lyrics_guide.html): jendela lirik, pembacaan lirik otomatis, dan lirik untuk lagu apa pun.
* [Antrean](queue_guide.html): apa yang diputar berikutnya.
* [Putar dari Tautan](play_from_url.html): memutar atau mengikuti apa pun dari tautan Spotify.
* [Perangkat](devices_guide.html): memindahkan pemutaran ke perangkat lain.
* [Fitur lain](misc_features.html): acak, ulangi, melompat dalam lagu, volume, berbagi tautan, timer tidur, dan pengumuman lagu.

## Pembaruan

Accessify Play diperbarui lewat Add-on Store NVDA (menu NVDA, Tools, Add-on Store), yang memberi tahu Anda bila ada versi baru. Setiap rilis juga diterbitkan di [GitHub Releases](https://github.com/InfiArtt/accessify-play/releases).

## Dukungan dan lisensi

Laporkan masalah dan ide di [GitHub](https://github.com/InfiArtt/accessify-play/issues). Jika add-on ini bermanfaat, Anda bisa mendukung pengembangannya lewat tombol **Donate** di pengaturan Accessify Play.

Lirik berasal dari [lrclib.net](https://lrclib.net), basis data lirik gratis yang dikelola komunitas, dengan lirik berstatus domain publik (CC0).

Accessify Play berlisensi [GNU General Public License v2.0](https://www.gnu.org/licenses/gpl-2.0.html).
