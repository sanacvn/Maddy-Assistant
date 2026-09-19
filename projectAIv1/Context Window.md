[[AI Engineer]]
### Definisi

**Context window** adalah jumlah maksimum token (input + output digabung) yang bisa "dilihat" model dalam satu kali proses. Ini termasuk system prompt, riwayat percakapan, dokumen yang kamu attach, sampai jawaban yang model hasilkan.

### Kenapa Gak Bisa Unlimited? (Ini Inti Pertanyaan Kamu)

**1. Kompleksitas komputasi self-attention itu O(n²)**

Inget score matrix di Part 4? Ukurannya `n × n`, di mana n = jumlah token. Artinya kalau context makin panjang, **biaya komputasi dan memori naik secara kuadratik**, bukan linear:

```
n = 1.000 token    →  ~1.000.000 pasangan attention
n = 10.000 token   →  ~100.000.000 pasangan attention   (100x lipat!)
n = 100.000 token  →  ~10.000.000.000 pasangan attention
```

Naik 10x panjang context = naik 100x biaya komputasi & memori attention. Ini alasan utama kenapa context window gak bisa asal digedein — makin panjang, makin mahal secara eksponensial (kuadratik), baik dari sisi kecepatan maupun kebutuhan GPU memory.

**2. KV Cache membengkak saat inference**

Waktu model generate token demi token, dia gak mau hitung ulang K dan V untuk semua token sebelumnya di tiap step (boros banget) — jadi K, V di-**cache**. Tapi cache ini ukurannya proporsional dengan `jumlah layer × jumlah head × dimensi × panjang context`. Context yang panjang = KV cache yang gede = kebutuhan GPU memory yang gede. Ini kendala **hardware**, bukan cuma kendala matematis.

**3. Positional encoding punya batas generalisasi**

Model dilatih dengan panjang context tertentu (misal maksimal sekian ribu token). Di luar panjang itu, encoding posisi (baik sinusoidal, learned, maupun RoPE) mulai **kurang akurat** merepresentasikan posisi — model "belum pernah lihat" pola posisi sejauh itu saat training. Ada trik-trik untuk memperpanjang ini setelah training (position interpolation, NTK-aware RoPE scaling, ALiBi, sliding window attention), tapi semuanya **trade-off**, bukan solusi sempurna tanpa batas.

**4. Biaya training**

Melatih model dengan context yang lebih panjang dari awal itu mahal — makin panjang sequence training, makin besar juga biaya komputasi kuadratik yang disebut di poin 1, dikali jutaan/miliaran contoh training. Ini kenapa provider model biasanya menaikkan context window secara bertahap dari generasi ke generasi, bukan langsung tak terhingga.

### Efek Samping: "Lost in the Middle"

Riset (mis. Liu, dkk.) menunjukkan fenomena: ketika context sangat panjang, model cenderung **lebih akurat mengambil informasi yang ada di awal atau akhir context**, dan **kurang akurat untuk informasi yang terkubur di tengah**. Ini karena distribusi attention "menipis" saat harus dibagi ke ribuan token sekaligus.

```
Akurasi retrieval info dalam context panjang (ilustrasi):

Awal context    ████████████████  tinggi
Tengah context   ████             rendah  ← "lost in the middle"
Akhir context    ███████████████  tinggi
```

**Implikasi praktis buat kamu**: jangan asal "jejalin" semua dokumen ke prompt (context stuffing) dan berharap model nangkep semuanya sama rata. Ini salah satu alasan kenapa **RAG** (retrieval yang selektif, ambil yang paling relevan aja) lebih efektif daripada dump semua dokumen mentah-mentah ke context.