---
created: '2026-07-25T19:02:33.376034'
tags: []
title: Kenapa Attention Muncul
---

# Kenapa Attention Muncul

[[AI Engineer]]

Part 1 — Dari RNN ke Transformer (Kenapa Attention Muncul)
Sebelum 2017, model bahasa itu dominan pakai RNN/LSTM. Cara kerjanya sequential — baca token 1, update "memori", baca token 2, update lagi, dst. Ada dua masalah besar:
1. Gak bisa diparalel. Karena token ke-5 butuh hasil dari token ke-4, GPU cuma bisa kerja satu langkah di satu waktu. Training jadi lambat banget buat data raksasa.
2. Long-range dependency hilang. Semakin jauh jarak dua kata dalam kalimat, semakin susah RNN "inget" hubungan antar keduanya (vanishing gradient). Kalimat panjang → informasi awal keburu "luntur".

Tahun 2017, paper "Attention Is All You Need" (Vaswani, dkk.) ngenalin arsitektur Transformer yang buang komponen recurrent sepenuhnya, diganti dengan mekanisme self-attention. Idenya: daripada baca token satu-satu secara berurutan, biarkan setiap token "melihat" semua token lain sekaligus, dan hitung semuanya secara paralel.

Ini dua keunggulan sekaligus:
- Paralel → training jauh lebih cepat di GPU/TPU.
- Direct connection antar token manapun, gak peduli jaraknya, jadi long-range dependency gak "luntur".

Ini adalah fondasi dari semua LLM modern: GPT, Claude, Llama, Gemini — semuanya varian Transformer.

Self-check: Kalau ditanya "kenapa Transformer menang lawan RNN?", jawaban intinya cuma dua kata: paralelisasi dan akses langsung ke semua token lain.