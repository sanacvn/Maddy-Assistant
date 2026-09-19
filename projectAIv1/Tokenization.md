

[[AI Engineer]]

  

DAY 1

Part 2 — Tokenization: Pintu Masuk ke Transformer

Model gak baca huruf atau kata utuh — model baca token. Token adalah potongan sub-kata hasil algoritma seperti BPE (Byte Pair Encoding) atau variannya.

Kenapa bukan per-karakter atau per-kata utuh?

Per-karakter: sequence jadi kepanjangan (mahal secara komputasi), dan model harus belajar dari nol pola huruf demi huruf.

Per-kata utuh: vocabulary meledak (bahasa Inggris aja punya ratusan ribu kata, belum lagi typo, nama, istilah teknis) dan model gak bisa handle kata yang belum pernah dilihat.

BPE ambil jalan tengah: kata umum jadi 1 token ("the", "adalah"), kata jarang dipecah jadi beberapa sub-token ("tokenization" → "token" + "ization").

Poin penting buat kamu: tokenizer LLM populer (kayak yang dipakai GPT-series) itu vocabulary-nya condong ke Bahasa Inggris, karena data training mayoritas Inggris. Konsekuensinya, teks Bahasa Indonesia sering butuh lebih banyak token untuk makna yang sama dibanding teks Inggris. Ini bakal kamu buktikan sendiri di Part 11 (latihan praktik).

Ini penting karena context window itu dihitung dalam token, bukan kata atau karakter — jadi efisiensi tokenisasi bahasa langsung mempengaruhi berapa banyak "muatan" yang bisa masuk ke prompt kamu