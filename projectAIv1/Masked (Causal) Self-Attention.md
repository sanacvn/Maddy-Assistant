[[AI Engineer]]

LLM seperti GPT, Claude, Llama itu **decoder-only** — artinya mereka generate teks satu token per satu token, dari kiri ke kanan. Konsekuensinya: saat memprediksi token ke-5, model **tidak boleh** mengintip token ke-6, ke-7, dst (karena saat inference nyata, token-token itu belum ada).

Makanya dipakai **causal mask**: skor attention untuk posisi "masa depan" dipaksa jadi `-infinity` sebelum softmax (sehingga setelah softmax jadi 0%).

```
            tok1   tok2   tok3   tok4
tok1  [     ✓      ✗      ✗      ✗   ]
tok2  [     ✓      ✓      ✗      ✗   ]
tok3  [     ✓      ✓      ✓      ✗   ]
tok4  [     ✓      ✓      ✓      ✓   ]
```

(✓ = boleh "dilihat", ✗ = di-mask jadi 0)

Ini kenapa LLM disebut **autoregressive**: prediksi token berikutnya cuma berdasar token-token sebelumnya, gak pernah "curi start" liat masa depan.