---
created: '2026-08-02T22:04:16.994144'
tags: []
title: Vector Similarity
---

# Vector Similarity
Link: [[Ai Engineer]]

Vector Similarity: Ngukur "Kemiripan Makna"
Setelah teks jadi vektor, gimana cara tau dua teks itu "mirip"? Jawabannya: ukur jarak/sudut antar vektornya secara matematis.

### Cosine Similarity (paling umum buat teks)
cosine(A, B) = (A · B) / (‖A‖ × ‖B‖)
- A · B = dot product (jumlah perkalian tiap komponen)
- ‖A‖, ‖B‖ = magnitude (panjang) tiap vektor

Hasilnya berkisar dari -1 (berlawanan total) sampai 1 (identik arah), tapi buat embedding teks biasanya jatuh di rentang 0–1.
Kenapa cosine, bukan langsung dot product? Karena cosine menormalisasi dulu berdasarkan panjang vektor — jadi yang diukur murni arah (makna), bukan magnitude (yang bisa dipengaruhi hal-hal gak relevan seperti panjang teks).

### Hitungan Manual
Ambil 3 kata dengan vektor toy:
- kucing = [0.90, 0.80, 0.10]
- anjing = [0.85, 0.75, 0.15]
- mobil  = [0.10, 0.20, 0.90]

Cosine similarity:
- cosine(kucing, anjing) = 0.9988 (sangat mirip)
- cosine(kucing, mobil)  = 0.3034 (jauh)
- cosine(anjing, mobil)  = 0.3489 (jauh)

### Euclidean Distance (alternatif)
euclidean(A, B) = √Σ(Aᵢ - Bᵢ)²
Mengukur jarak garis lurus antar titik di ruang vektor (makin kecil = makin mirip). Untuk data teks, cosine biasanya lebih disukai karena fokus ke arah/makna.