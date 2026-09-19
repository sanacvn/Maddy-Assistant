---
created: '2026-06-04T21:10:12.496462'
tags: []
title: Spark MLlib
---

# Spark MLlib
[[NoSQL]]

Spark MLlib?
MLlib adalah pustaka ( library) machine learning bawaan dari Apache Spark yang dirancang khusus supaya bisa menangani data berskala sangat besar (big data) dengan efisien. Pustaka ini sudah ada sejak Spark versi 0.8 dan bisa dipakai menggunakan bahasa Java, Scala, maupun Python.  

Meski awalnya dibangun menggunakan format RDD, sekarang MLlib sangat menyarankan penggunaan format DataFrame (sering disebut sebagai "Spark ML") karena lebih modern, sementara versi RDD hanya dipertahankan untuk pemeliharaan saja. Pustaka ini sama sekali tidak berstatus deprecated atau usang.  

Mengingat Kembali Konsep Machine Learning
Machine Learning adalah algoritma yang belajar dari sebuah data untuk mengenali pola dan mengambil keputusan secara otomatis. Terdapat tiga jenis utama, yaitu:  

Supervised Learning: Model dilatih menggunakan data yang sudah memiliki label atau kunci jawaban. Contohnya adalah Klasifikasi untuk mengelompokkan email sebagai spam atau non-spam, serta Regresi untuk memprediksi angka seperti prediksi harga rumah atau tinggi badan seseorang.  

Unsupervised Learning: Model mencari pola sendiri dari data yang tidak punya label. Contohnya adalah Klastering menggunakan algoritma K-Means untuk mengelompokkan objek yang mirip.  

Reinforcement Learning: Model terus belajar dari aksi yang dilakukan berdasarkan umpan balik berupa hadiah (reward) atau penalti.  

Kenapa Memilih Spark MLlib?
Kalau kamu mengolah data berukuran terabyte, algoritma biasa akan sangat lambat. Spark MLlib sangat cocok untuk data scientist karena:
Berjalan di atas mesin Apache Spark yang populer dan cepat.  

Bisa memproses data hingga 100 kali lebih cepat daripada Hadoop MapReduce jika dilakukan di dalam memori (in-memory), atau 10 kali lebih cepat jika di disk.  

Sangat ringan, mudah dipahami, dan mendukung caching untuk menghindari pemindahan data yang tidak perlu.  

Komponen Penting di Spark MLlib (DataFrame API)
Biar gampang dipakai dan alurnya jelas, MLlib menggunakan beberapa komponen utama dalam pengolahan datanya:
DataFrame: Tipe data dari Spark SQL yang fleksibel untuk diproses secara paralel, mirip seperti tabel database yang isinya bisa berupa teks, vektor, atau gambar.  

Transformer: Algoritma yang berfungsi mengubah satu DataFrame menjadi DataFrame baru, biasanya dengan cara menambah kolom baru. Algoritma ini berjalan menggunakan fungsi transform().  

Estimator: Ini adalah algoritma pembelajaran yang belum dilatih, contohnya algoritma Logistic Regression. Algoritma ini memproses data latih menggunakan perintah fit() untuk menghasilkan sebuah model.  

Parameter: Pengaturan manual yang bisa kamu terapkan pada Estimator atau Transformer.  

Pipeline: Rangkaian langkah-langkah (stage) yang menggabungkan Transformer dan Estimator menjadi satu alur yang berurutan.  

Contoh Alur Kerja Pipeline
Pipeline berfungsi memastikan bahwa data yang dipakai saat pelatihan dan data baru yang dipakai saat pengujian melewati langkah pemrosesan yang sama persis.  

Saat Pelatihan (Training): Pipeline bertindak sebagai Estimator. Contohnya, teks mentah masuk ke dalam fungsi Tokenizer -> lalu diubah oleh HashingTF -> lalu dimasukkan ke dalam algoritma Logistic Regression menggunakan perintah fit().  

Hasil Akhir: Proses di atas akan menghasilkan sebuah PipelineModel.  

Saat Pengujian (Testing): PipelineModel ini sekarang berubah peran menjadi Transformer. Ketika ada data teks baru, kamu tinggal menjalankan perintah transform(), dan data tersebut akan otomatis melewati proses Tokenizer dan HashingTF yang sama untuk menghasilkan prediksi klasifikasi akhir