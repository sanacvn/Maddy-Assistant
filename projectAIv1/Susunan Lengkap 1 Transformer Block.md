[[AI Engineer]]

Setelah attention, ada beberapa komponen lain yang disusun jadi satu "block", dan block ini **ditumpuk berkali-kali** (N layer — makin besar model, makin banyak layer-nya):

Input token
     │
     ▼
(Token Embedding) +( Positional Encoding)
     │
     ▼
┌───────────────────────────────┐
│  Masked Multi-Head Attention   │
└───────────────────────────────┘
     │
     ▼
  Add (residual connection) & LayerNorm
     │
     ▼
┌───────────────────────────────┐
│  Feed-Forward Network          │
│  (Linear → Activation → Linear)│
└───────────────────────────────┘
     │
     ▼
  Add (residual connection) & LayerNorm
     │
     ▼
  (ulangi block ini N kali, ditumpuk)
     │
     ▼
  Linear → Softmax → distribusi probabilitas token berikutnya



Dua komponen yang belum dibahas:

- **Residual connection ("Add")**: output tiap sub-layer dijumlahkan dengan input aslinya (`output = SubLayer(x) + x`). Ini membantu gradien mengalir lancar ke layer yang dalam saat training (mencegah vanishing gradient di jaringan yang sangat dalam).
- **Layer Normalization**: menormalisasi nilai supaya training lebih stabil dan cepat konvergen.
- **Feed-Forward Network**: setelah attention "mencampur" info antar token, FFN memproses tiap token **secara independen**, menambah kapasitas non-linear model untuk "berpikir" lebih dalam tentang representasi tiap token.

Setelah lewat N block, hasil akhirnya diproyeksikan ke ukuran vocabulary dan lewat softmax → jadi **distribusi probabilitas untuk token berikutnya**. Token dipilih (lewat sampling/greedy/dll), lalu diulang lagi buat prediksi token setelahnya