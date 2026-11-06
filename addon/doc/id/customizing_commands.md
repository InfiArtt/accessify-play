# Mengubah perintah dan pintasan

Anda bisa mengubah tombol yang menjalankan setiap perintah di lapisan, dan apakah lapisan tetap terbuka sesudahnya; juga pintasan di dalam jendela Accessify Play.

## Membuka editor

Tekan `NVDA+Alt+G`, lalu `F2`. **Command Layer Editor** menampilkan semua perintah dalam empat kolom:

* **Command**: nama perintah, misalnya Play/Pause.
* **Shortcut**: tombol yang menjalankannya di dalam lapisan.
* **Keep Open**: apakah lapisan tetap terbuka setelah perintah dijalankan.
* **Description**: apa yang dilakukan perintah itu.

## Mengubah perintah

1. Pilih perintahnya lalu tekan `Enter`, atau tombol **Edit**.
2. Di **Shortcut**, ketik tombol yang ingin dipakai, misalnya `p` atau `shift+d`. Tombol khusus diketik dengan namanya: `space`, `leftArrow`, `pageUp`, `end`, `f12`, dan seterusnya. Kosongkan untuk mengeluarkan perintah dari lapisan.
3. Centang **Keep layer open after executing** jika Anda ingin bisa langsung menekan perintah itu lagi, seperti untuk volume atau melewati lagu.
4. Tekan OK.

**Reset to Defaults** mengembalikan semua perintah ke tombol dan pengaturan Keep Open aslinya, setelah bertanya kepada Anda.

Saat editor ditutup setelah ada perubahan, tombol baru langsung berfungsi; NVDA tidak perlu dimulai ulang.

`F1`, `F2`, dan `Escape` selalu punya fungsi yang sama di lapisan dan tidak bisa diubah. Satu tombol hanya bisa menjalankan satu perintah: jika Anda memilih tombol yang sudah dipakai perintah lain, editor menyebutkan perintah itu dan meminta Anda memilih tombol lain.

## Pintasan tanpa lapisan

Untuk menjalankan perintah dengan satu gestur, tanpa menekan `NVDA+Alt+G` lebih dulu, tetapkan gesturnya di dialog Input Gestures NVDA (menu NVDA, Preferences, Input Gestures), di bawah **Accessify Play**. `NVDA+Alt+G` sendiri juga bisa diubah di sana ("Accessify Play layer commands").


## Pintasan di dalam jendela

Pintasan di dalam jendela Accessify Play, seperti `Alt+P` untuk memutar item yang dipilih, juga bisa diubah. Buka menu NVDA, lalu Preferences, Settings, pilih kategori **Accessify Play**, dan tekan **Window Shortcuts...**. Daftarnya menampilkan setiap tindakan beserta tombolnya:

1. Pilih sebuah tindakan lalu tekan `Enter`, atau **Change...**.
2. Ketik tombolnya seperti cara NVDA menulisnya, misalnya `alt+p`, `ctrl+shift+tab`, atau `f5`. Tombol khusus diketik dengan namanya: `tab`, `enter`, `space`, `backspace`, `delete`, `insert`, `home`, `end`, `pageUp`, `pageDown`, `upArrow`, `downArrow`, `leftArrow`, `rightArrow`, `f1` sampai `f24`. Beberapa tombol dipisahkan dengan spasi; kosongkan kolomnya untuk tanpa pintasan.
3. Tekan OK, lalu OK di dialog Window Shortcuts dan di pengaturan NVDA untuk menyimpan. Jendela yang dibuka sesudahnya memakai tombol baru.

Beberapa aturan menjaga agar tombol tidak saling mengganggu:

* Pintasan yang berlaku di mana saja dalam sebuah jendela memerlukan `Alt` atau `Ctrl`, atau harus berupa tombol fungsi, agar tidak mengganggu pengetikan di kolom pencarian.
* Tombol untuk memindahkan dan menghapus trek di Pustaka hanya berlaku di daftar treknya, jadi boleh tombol apa saja, seperti `delete`.
* Untuk berpindah ke jenis pencarian atau tab dengan angka, ketik hanya tombol yang ditahan bersama angka, seperti `ctrl` (untuk `Ctrl+1`, `Ctrl+2`, dan seterusnya) atau `alt+shift`.
* Satu tombol hanya bisa dimiliki satu tindakan. Jika Anda memilih tombol yang sudah dimiliki tindakan lain, Anda diberi tahu tindakan mana.
* Huruf bergaris bawah pada tombol (seperti `Alt+C` untuk Close) bukan pengaturan. Jika Anda memberi pintasan huruf sebuah tombol, pintasannya yang menang di jendela itu dan tombol tersebut tidak lagi menampilkan huruf itu, sehingga NVDA tidak mengumumkan tombol yang tidak akan menekannya. Tombol yang melakukan hal yang sama dengan pintasan, seperti Play Selected untuk `Alt+P`, tetap memiliki hurufnya.

**Reset to Defaults** mengembalikan semua pintasan, setelah bertanya kepada Anda.

Pintasan ini juga merupakan pengaturan di `nvda.ini`, di bawah `[spotify]`, jika Anda lebih suka mengubahnya di sana. Tombol yang tidak bisa menjadi pintasan diabaikan, dan nilai bawaannya dipakai.

* `keyPlay` (bawaan `alt+p`): memutar item yang dipilih, di setiap jendela yang berisi daftar.
* `keyQueue` (bawaan `alt+q`): memasukkan item yang dipilih ke antrean.
* `keyCopyLink` (bawaan `alt+l`): menyalin tautan Spotify item yang dipilih.
* `keyLyrics` (bawaan `alt+w`): menampilkan lirik lagu yang dipilih: di Pencarian, album, playlist, jendela artis, Pustaka, dan antrean.
* `keyRefresh` (bawaan `alt+r`): memuat ulang daftar, di Pustaka dan antrean.
* `keyFollow` (bawaan `alt+f`): di Pencarian, mengikuti atau berhenti mengikuti artis yang dipilih.
* `keyDiscography` (bawaan `alt+d`): di Pencarian, membuka diskografi artis yang dipilih.
* `keySearchField` (bawaan `ctrl+f`): di Pencarian, kembali ke kolom pencarian.
* `keyNextTab` (bawaan `ctrl+tab ctrl+pageDown`): jenis pencarian berikutnya, atau tab berikutnya di jendela artis atau Pustaka.
* `keyPreviousTab` (bawaan `ctrl+shift+tab ctrl+pageUp`): jenis pencarian atau tab sebelumnya.
* `keyTabNumber` (bawaan `ctrl`): ditahan bersama angka, berpindah ke jenis pencarian atau tab tersebut.
* `keySaveEpisode` (bawaan `alt+s`): di daftar episode sebuah acara, menyimpan atau batal menyimpan episode yang dipilih.
* `keyNewPlaylist` (bawaan `ctrl+n`): di Pustaka, membuat playlist.
* `keyMoveTrackUp` (bawaan `alt+upArrow`) dan `keyMoveTrackDown` (bawaan `alt+downArrow`): di Pustaka, memindahkan trek playlist Anda sendiri.
* `keyRemoveTrack` (bawaan `delete`): di Pustaka, menghapus trek dari playlist Anda sendiri.

---
[Kembali ke Tombol perintah](keybindings.html)
