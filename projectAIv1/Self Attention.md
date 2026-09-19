[[AI Engineer]]

### Intuisi

Bayangkan kamu baca kalimat: **"Kucing itu tidur di sofa karena dia lelah."**

Kata **"dia"** merujuk ke apa? Otak kamu otomatis "menoleh" balik ke kata **"Kucing"**. Itu persis yang dilakukan self-attention: setiap token menghitung **seberapa relevan** token lain terhadap dirinya, lalu "menyerap" informasi dari token-token yang relevan itu.

### Query, Key, Value — Analogi Search Engine

Bayangkan sistem pencarian:

- **Query (Q)** = apa yang kamu cari ("aku lagi butuh info apa?")
- **Key (K)** = label/index dari setiap dokumen ("dokumen ini isinya tentang apa?")
- **Value (V)** = isi sebenarnya dari dokumen itu

Tiap token menghasilkan Q, K, V-nya sendiri lewat perkalian dengan weight matrix yang **dipelajari saat training**: `Q = X·Wq`, `K = X·Wk`, `V = X·Wv`.

### Langkah Matematis Self-Attention

```
Attention(Q, K, V) = softmax( Q · Kᵀ / √d_k ) · V
```

Step by step:

1. **Score = Q · Kᵀ** — tiap query "dicocokkan" dengan tiap key lewat dot product. Skor tinggi = token itu relevan satu sama lain.
2. **Scale (bagi √d_k)** — kalau dimensi (d_k) besar, hasil dot product bisa jadi sangat besar, bikin softmax "jenuh" (gradiennya nyaris nol, training jadi susah). Pembagian ini menjaga skala tetap stabil.
3. **Softmax** — ubah skor jadi distribusi probabilitas (jumlah semua = 100%). Ini yang disebut **attention weight** — seberapa besar "perhatian" satu token ke token lainnya.
4. **Kalikan dengan V** — weighted sum. Output tiap token = campuran informasi dari semua token lain, dibobotkan sesuai attention weight-nya.

### Contoh Hitungan Manual (Biar Beneran Nempel)

Ambil kalimat sederhana 3 token: **"Saya" "suka" "AI"**. Kita sederhanakan dimensi embedding jadi 2 (di model asli bisa ribuan), dan supaya gampang dihitung tangan, anggap dulu `Wq = Wk = Wv = matriks identitas` (jadi Q = K = V = X). Di model asli, ketiga matriks ini **beda dan dipelajari** — ini cuma biar kamu bisa lihat mekanismenya tanpa keriting duluan.

```
X (embedding toy):
Saya = [1, 0]
suka = [0, 1]
AI   = [1, 1]

Q = K = V = X (karena W = identitas)
```

**Step 1 — Score = Q · Kᵀ:**

```
            Saya   suka   AI
Saya   [    1      0      1   ]
suka   [    0      1      1   ]
AI     [    1      1      2   ]
```

**Step 2 — Scale (÷ √d_k, d_k = 2, jadi ÷ 1.414):**

```
            Saya    suka    AI
Saya   [   0.71    0.00    0.71 ]
suka   [   0.00    0.71    0.71 ]
AI     [   0.71    0.71    1.41 ]
```

**Step 3 — Softmax tiap baris** (ubah jadi persentase perhatian):

```
            Saya    suka    AI
Saya   [   40%     20%     40%  ]
suka   [   20%     40%     40%  ]
AI     [   25%     25%     50%  ]
```

Baca baris "Saya": token **"Saya"** kasih 40% perhatian ke dirinya sendiri, 20% ke "suka", 40% ke "AI".

**Step 4 — Output = weights · V:**

```
Output("Saya") = 0.40×[1,0] + 0.20×[0,1] + 0.40×[1,1] = [0.80, 0.60]
Output("suka") = 0.20×[1,0] + 0.40×[0,1] + 0.40×[1,1] = [0.60, 0.80]
Output("AI")   = 0.25×[1,0] + 0.25×[0,1] + 0.50×[1,1] = [0.75, 0.75]
```

Perhatikan: vektor output token **"Saya"** sekarang **bukan lagi murni [1,0]** — dia udah "menyerap" sedikit informasi dari "suka" dan "AI". Inilah yang bikin representasi token jadi **kontekstual** — kata yang sama bisa punya representasi beda tergantung kalimatnya.

> Nanti di Part 11 kamu akan jalanin ini pakai numpy beneran, biar makin nempel.

**Self-check:** Kenapa perlu dibagi √d_k sebelum softmax? → Supaya nilai dot product gak terlalu besar dan bikin softmax jenuh (gradien mendekati nol), yang bikin training gak stabil