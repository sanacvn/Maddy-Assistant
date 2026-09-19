---
created: "[[NoSQL]]"
tags: []
title: Apache Spark & Ekosistemnya
---

Apa itu Apache Spark & Ekosistemnya?
Apache Spark itu pada dasarnya adalah sistem canggih yang dirancang buat memproses data dalam volume super besar secara efisien dan cepat. Bahasa aslinya ditulis pakai Scala, tapi bisa juga dipakai dengan Java, Python, dan R.  

Spark punya "otak" utama bernama Spark Core yang ngurusin memori, penjadwalan tugas, dan pemulihan error. Di atas fondasi ini, ada beberapa pilar pendukung:  

Spark SQL: Buat nge-kueri data secara interaktif (mirip bahasa SQL biasa).  
Spark Streaming: Buat analisis data real-time (langsung saat itu juga).  
MLlib: Pustaka (library) khusus buat Machine Learning.  
GraphX: Buat pemrosesan data berbentuk graf.  

2. Kenalan dengan PySpark
Karena kita suka pakai Python yang gampang dan kodenya rapi, Spark bikin API khusus buat Python bernama PySpark.  
Keuntungannya? Python itu gampang dipelajari, perawatannya mudah, dan dukungan visualisasi datanya jauh lebih kaya dibanding kalau kita pakai Java atau Scala.  

Instalasinya: Kalau di lokal, kamu butuh Java 8, download file Spark, atur Environment Variables (seperti JAVA_HOME, SPARK_HOME). Tapi kalau mau praktis, kamu bisa jalanin PySpark di Google Colab dengan menginstal dependencies seperti openjdk-8 dan pake library findspark.  

3. Mengolah Data (DataFrame & Spark SQL) Beserta Contohnya
Ini bagian praktisnya. Di PySpark, data terstruktur biasanya disimpan dalam bentuk DataFrame (mirip tabel di database relasional).  

A. Membaca dan Melihat Data
Load Data: Kamu bisa membaca file CSV masuk ke DataFrame. Parameter header=True artinya baris pertama itu nama kolom, dan sep=";" itu pemisahnya.
Contoh: df = spark.read.csv('cars.csv', header=True, sep=";")   

Melihat Isi Data: Jangan pakai df.collect() kalau datanya raksasa karena bisa bikin sistem nge-crash. Paling aman pakai df.show().
Contoh: df.show(5) untuk melihat 5 baris pertama, atau df.show(5, truncate=False) biar teksnya nggak kepotong.  

B. Mengecek Skema (Tipe Data)
Kamu harus tahu tipe data di tiap kolom, apakah dia teks, angka desimal, dsb.
Cara ngecek: Pakai df.printSchema().  

Biar otomatis: Pas baca data CSV, kamu bisa tambahin inferSchema=True biar Spark otomatis nebak tipe datanya (misal otomatis deteksi angka atau string).  

C. Menggunakan Kueri SQL di DataFrame
Kerennya Spark, kamu nggak harus melulu pakai fungsi bawaan Python. Kamu bisa nulis sintaks SQL persis kayak di database.
Langkah 1: Ubah dulu DataFrame kamu jadi tabel sementara (temporary view).
Contoh: df.createOrReplaceTempView("my_table").  

Langkah 2: Tulis kueri SQL-nya pakai spark.sql().
Contoh: result = spark.sql("SELECT * FROM my_table WHERE Model == 70") lalu jalankan result.show().  

D. Kueri Lanjutan (Subquery & Window Function)
Spark SQL juga jago menangani kueri yang kompleks:
Subquery: Berguna kalau kamu mau memfilter data berdasarkan hasil kueri lain.
Contoh Kasus: Mencari nama karyawan yang gajinya di atas rata-rata.
Contoh Sintaks: SELECT name FROM employees WHERE id IN (SELECT id FROM salaries WHERE salary > (SELECT AVG(salary) FROM salaries)).  

Window Function: Berguna untuk menghitung sesuatu (misal ranking atau total) berdasarkan kelompok tertentu, tanpa menggabungkan barisnya.
Contoh Kasus: Bikin ranking gaji tertinggi di tiap departemen. Pakai Window.partitionBy("department").orderBy(F.desc("salary")) dan hitung dengan F.rank()