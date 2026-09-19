[[AI Engineer]]

**Hallucination** = model menghasilkan informasi yang terdengar meyakinkan tapi salah/gak akurat/gak ada dasarnya.

Ini bukan "bug" yang bisa di-patch gampang — ini **konsekuensi langsung dari cara LLM dibangun dan dilatih**. Beberapa akar penyebabnya:

**1. Model adalah predictor token berikutnya, bukan mesin pencari fakta.** Yang dipelajari model saat training adalah: "dengan konteks ini, token apa yang paling mungkin muncul selanjutnya?" — bukan "apakah pernyataan ini benar secara faktual?". Objective training-nya itu **probabilistik**, bukan **verifikasi kebenaran**.

**2. Gak ada mekanisme grounding real-time bawaan.** Tanpa tool tambahan (search, RAG, database), model cuma mengandalkan apa yang "terkompresi" di dalam parameternya dari data training — yang punya batas waktu (knowledge cutoff) dan gak selalu lengkap/akurat.

**3. Model punya "kepercayaan diri" default, bukan "aku gak tau".** Karena tugasnya menghasilkan token yang plausible, model cenderung tetap menjawab dengan nada yakin walau informasinya sebenarnya lemah atau gak ada di data trainingnya — kecuali dilatih/di-instruksikan secara eksplisit untuk mengenali ketidaktahuan.

**4. Noise dan bias di data training.** Kalau ada kesalahan, mitos, atau bias di data yang dipakai training, kemungkinan itu terpelajar dan tereproduksi.

**5. Context window yang penuh/panjang ikut memperparah.** Balik ke Part 8 — efek "lost in the middle" bisa bikin model "lupa" instruksi atau fakta yang sudah kamu kasih di awal prompt kalau context-nya kepanjangan, sehingga model "mengarang" jawaban yang sebetulnya sudah ada groundnya, tapi keburu "tenggelam" di tengah context.

### Cara Mitigasi (Preview Buat Roadmap LangChain Kamu)

- **RAG (Retrieval-Augmented Generation)** — kasih model dokumen relevan yang di-retrieve secara selektif saat itu juga, biar jawaban di-_ground_ ke sumber nyata, bukan cuma dari memori parametrik.
- **Tool use / function calling** — biarkan model manggil search engine, kalkulator, atau database buat verifikasi, bukan menebak.
- **Prompting yang baik** — instruksikan model untuk bilang "gak tau" kalau memang gak ada informasinya, daripada maksa jawab.
- **Citation/sourcing** — minta model mengaitkan klaim dengan sumber spesifik, biar lebih gampang diverifikasi manusia.