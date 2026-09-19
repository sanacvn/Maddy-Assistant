[[AI Engineer]]

Satu "attention head" cuma bisa fokus ke **satu jenis relasi** dalam satu waktu. Padahal bahasa itu multi-layer — ada relasi sintaksis (subjek-predikat), relasi semantik (sinonim, topik), relasi koreferensi (kata ganti merujuk ke apa), dst.

Solusinya: **pecah** Q, K, V jadi beberapa "kepala" (head) yang lebih kecil, hitung attention di tiap head **secara paralel**dengan weight matrix berbeda-beda, lalu gabungkan hasilnya.

```
MultiHead(Q,K,V) = Concat(head₁, head₂, ..., head_h) · Wᴼ

dimana head_i = Attention(Q·Wᵢᵠ, K·Wᵢᴷ, V·Wᵢⱽ)
```

Analoginya: bayangkan kamu baca kalimat dengan **beberapa "kacamata" berbeda sekaligus** — satu kacamata fokus ke struktur gramatikal, satu lagi fokus ke makna kata, satu lagi fokus ke siapa-merujuk-ke-siapa. Model modern biasanya punya belasan sampai puluhan head per layer.