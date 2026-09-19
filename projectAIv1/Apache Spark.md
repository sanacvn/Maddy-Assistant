---
created: "[[NoSQL]]"
tags: []
title: Apache Spark
---

#  Apache Spark
[[Spark MLlib]]
[[Apache Spark & Ekosistemnya]]

Apache Spark itu ibarat mesin super ngebut untuk memproses data berskala besar.

**Super Cepat:** Spark memproses data langsung di dalam memori utama atau RAM (in-memory processing) sehingga nggak perlu bolak-balik baca hard disk. Karena hal ini, Spark bisa 100x lebih cepat dari pendahulunya yaitu Hadoop MapReduce saat memproses di memori, dan 10x lebih cepat kalau memproses di disk.

**Serba Bisa:** Spark mendukung berbagai bahasa pemrograman, seperti Java, Scala, Python, dan R.

**Fitur Lengkap:** Di dalamnya udah ada paket lengkap seperti Spark SQL (buat query), MLlib (buat machine learning), GraphX (buat graf), dan Streaming (buat data real-time).

### Komponen Penting di Spark:
- **Driver Program & Spark Context:** Ini adalah "bos" atau titik masuk utama yang mengatur tugas, nyambungin ke sistem cluster, dan bagi-bagi resource memori/CPU.
- **Cluster Manager:** Manajer yang ngurusin sumber daya, contohnya YARN, Mesos, atau Kubernetes.
- **Executor:** Pekerja di lapangan (worker node) yang tugasnya langsung mengeksekusi perintah atau tasks.

### Apa itu RDD?
Di Spark, ada yang namanya RDD (Resilient Distributed Datasets). Ini adalah bentuk struktur data dasar di Spark.

RDD ini sifatnya anti-gagal (fault-tolerant), jadi kalau ada data yang hilang pas diproses, sistem bisa balikin datanya secara otomatis.

Data di RDD disebar (distributed) di banyak komputer/node sekaligus biar prosesnya ringan.

Operasinya ada dua macam: Transformation (bikin data baru, seperti memfilter data dengan perintah filter()) dan Action (mengeluarkan hasil perhitungan, seperti perintah count() buat ngitung jumlah).

### 2. Batch Processing vs Streaming Processing
Ini bedanya cara kita nanganin data yang masuk:

**Batch Processing:** Data diproses secara borongan atau dalam jumlah besar pada waktu tertentu yang berkala (misalnya tiap malam atau seminggu sekali). Ini cocok banget buat bikin laporan bulanan atau agregasi data.

**Streaming Processing:** Data diproses saat itu juga secara real-time atau dipotong jadi micro-batch (batch super kecil). Ini cocok buat deteksi anomali (misal: mendeteksi kalau ada transaksi kartu kredit yang mencurigakan secara instan) atau monitoring sistem.

Mengapa kita harus tahu bedanya? Biar kita bisa sesuaikan dengan kebutuhan bisnis, waktu respons yang dimau, desain infrastruktur, dan seberapa ribet pengelolaannya.

### 3. Spark Streaming & Structured Streaming
Spark juga punya alat buat nangkap data real-time:

**Spark Streaming:** Fitur ini membagi aliran data yang masuk menjadi batch kecil-kecil (micro-batch) untuk diproses secara berkala.

**Structured Streaming:** Ini adalah versi modern dari Spark Streaming. Cara pakainya jauh lebih gampang karena kita cukup nulis query deklaratif kaya SQL, dan Spark bakal otomatis ngurusin kerumitan di belakang layarnya (seperti manajemen jadwal micro-batch dan fault tolerance).

### Contoh Kasus Sederhana:
Bayangin kita mau menganalisis kata kunci trending topic di media sosial. Aliran tweet orang-orang yang ngetik kata "pemilu" atau "harga BBM" ditangkap terus-menerus dan dikirim ke mesin Kafka. Lalu, Spark Streaming bakal ngambil data tweet tersebut setiap beberapa detik, memfilter bahasanya, dan menghitung kata apa yang paling banyak diomongin saat itu juga. Hasilnya langsung ditampilin ke dashboard.

### 4. Kenalan dengan Apache Kafka
Kafka adalah sebuah platform buat ngumpulin dan mengirimkan aliran data (streaming) secara real-time secara terdistribusi. Ibaratnya, Kafka ini kurir super cepat yang ngangkut paket data.

**Komponen Utama Kafka:**
- **Producer:** Pihak yang memproduksi atau mengirimkan data ke Kafka. Contoh: Aplikasi toko online yang mengirimkan data klik dari pengunjung.
- **Topic:** Kategori atau saluran tempat pesan tersebut disimpan. Ibarat "Grup Chat", pengirim masukin pesan ke topik tertentu, dan penerima baca dari topik tersebut.
- **Broker:** Server Kafka yang tugasnya menyimpan data-data tersebut.
- **Consumer:** Aplikasi penerima yang mengambil dan membaca data dari Kafka.

### Kesimpulan Kerjasama Spark dan Kafka:
Jadi, Kafka tugasnya menyuplai data real-time yang masuk tanpa henti, lalu Spark yang bertugas mengambil data tersebut, mengolahnya dengan Structured Streaming, dan merangkum hasilnya biar bisa dibaca atau disimpan oleh bisnis kamu. Mereka berdua adalah bestie di dunia ekosistem Big Data