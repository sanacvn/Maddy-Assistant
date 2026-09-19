---
created: 2026-06-04T16:14:00.504863
tags: []
title: NoSQL
---

# NoSQL Overview

## 1. Pengenalan NoSQL & Mengapa RDBMS Mulai Ditinggalkan
NoSQL artinya "Not only SQL". RDBMS (MySQL/PostgreSQL) kaku untuk data internet yang masif, renggang, dan tidak terstruktur.

**Karakteristik Utama NoSQL:**
- **Skalabilitas Horizontal:** Menambah mesin baru (Horizontal Scaling) daripada meningkatkan spek satu mesin (Vertical Scaling).
- **Fokus pada Kinerja & Distribusi:** Optimal untuk data tersebar di banyak mesin.

## 2. 4 Tipe Utama Database NoSQL
- **Key-Value Store:** Pasangan Kunci-Nilai (Redis, Dynamo, Cassandra). Contoh: Caching.
- **Document Database:** Format JSON/BSON (MongoDB, CouchDB). Contoh: Profil e-commerce.
- **Column-Oriented Store:** Berbasis kolom (HBase, Bigtable). Contoh: Analisis log transaksi.
- **Graph Database:** Node & Edge (Neo4j, AllegroGraph). Contoh: Jaringan sosial.

## 3. Teorema CAP
Database terdistribusi memilih 2 dari 3:
- **C (Consistency):** Data sama di semua tempat.
- **A (Availability):** Sistem selalu aktif.
- **P (Partition Tolerance):** Tetap jalan meski ada gangguan jaringan.
*Contoh: MongoDB (CP), Cassandra/CouchDB (AP).*

## 4. Bedah Teknologi: Neo4j
Dirancang untuk data terhubung.
- **Komponen:** Node, Relationship, Property.
- **Bahasa Kueri:** Cypher (CQL).
- **Contoh:** `MATCH (p:Person)-[:DIRECTED]->(m:Movie) WHERE m.released > 2010 RETURN p`