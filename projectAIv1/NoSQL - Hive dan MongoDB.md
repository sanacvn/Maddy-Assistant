---
created: "[[NoSQL]]"
tags: []
title: NoSQL - Hive dan MongoDB
---

B. Apache Hive (Data Warehouse untuk Big Data)
Hive sebenarnya adalah infrastruktur data warehouse yang dibangun di atas Hadoop. Dia dibuat agar orang yang tidak bisa bahasa pemrograman Java tetap bisa mengolah data besar menggunakan perintah mirip SQL.
Bahasa Kueri: Menggunakan HiveQL (HQL). Hive akan menerjemahkan perintah HQL ini menjadi tugas MapReduce yang berjalan di kluster Hadoop.
Karakteristik Unik: Menggunakan sistem Schema-on-Read. Artinya, skema atau aturan tabel baru akan diterapkan saat data dibaca (waktu kueri), bukan saat data dimasukkan (Schema-on-Write seperti RDBMS). Ini bikin proses input data jadi super cepat.

C. MongoDB (Document Database)
MongoDB adalah salah satu database NoSQL paling populer di dunia. Data di dalamnya disimpan dalam format biner JSON yang disebut BSON.
Struktur Data: Database → Koleksi → Dokumen → Field (Key-Value).
Kelebihan: Kecepatannya diklaim 2 sampai 10 kali lebih cepat daripada MySQL karena tidak ada sistem join yang memperlambat performa.
Fitur Canggih:
GridFS: Fitur untuk memotong file biner berukuran besar (misal video/gambar) menjadi pecahan-pecahan kecil berukuran 256KB agar bisa disimpan langsung di dalam database.
Sharding: Membagi dokumen ke dalam beberapa partisi mesin secara otomatis (horizontal partitioning) berdasarkan Shard Key agar beban kerja database seimbang (load balancing).
Replika & Arbiter: MongoDB menduplikasi data ke beberapa mesin (Primary & Secondary). Jika mesin utama (Primary) mati, sebuah komponen kecil bernama Arbiter akan ikut memilih mesin Secondary mana yang layak naik jabatan menggantikan mesin utama.