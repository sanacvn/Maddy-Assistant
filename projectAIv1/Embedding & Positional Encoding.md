[[AI Engineer]]

### Token → Vector

Setiap token diubah jadi vektor angka berdimensi tinggi (misal 768, 4096, dst — makin besar model, makin besar dimensinya) lewat **embedding layer**. Vektor ini adalah representasi makna token dalam ruang matematis — token dengan makna mirip akan punya vektor yang "berdekatan".

### Kenapa Butuh Positional Encoding?

Ini bagian yang sering kelewat dipahami. Self-attention (yang bakal kita bedah di Part 4) itu sifatnya **permutation-invariant** — artinya kalau urutan token diacak, hasil komputasi attention-nya (secara matematis) gak berubah. Padahal urutan kata itu krusial:

```
"Kucing makan ikan"  ≠  "Ikan makan kucing"
```

Makna berubah total padahal token-nya sama. Makanya sebelum masuk ke attention, tiap token embedding **ditambah**dengan **positional encoding** — semacam "cap waktu" yang bilang "aku ini token urutan ke berapa".

Beberapa pendekatan:

- **Sinusoidal (original 2017 paper)**: pakai fungsi sin/cos dengan frekuensi berbeda per dimensi.
- **Learned positional embedding**: posisi juga jadi vektor yang dipelajari saat training (seperti GPT-2).
- **RoPE (Rotary Position Embedding)**: dipakai banyak LLM modern (Llama, dkk) — encode posisi dengan cara "merotasi" vektor Q dan K, sehingga yang dipelajari adalah **posisi relatif** antar token, bukan posisi absolut. Ini punya sifat generalisasi yang lebih baik ke context panjang (walau tetap ada batasnya — kita bahas di Part 8).

> Catatan: implementasi detail positional encoding beda-beda tiap provider model (OpenAI, Anthropic, Meta, dst) dan gak semua dipublikasikan detail. Yang penting kamu paham **konsepnya**: tanpa positional encoding, Transformer itu buta terhadap urutan.