# Telegram AI Agent with Gemini

Agent Telegram ini memakai Gemini sebagai model utama dan bisa memanggil tool untuk:

- Notion
- Google Docs
- Google Calendar
- Browser internet

## Fitur

- Chat dua arah di Telegram
- Function calling ke tool lokal
- Cari dan buat page di Notion
- Baca dan tulis context store di Google Docs
- Lihat dan buat event di Google Calendar
- Search web dan buka halaman web untuk diambil ringkasannya

## Stack

- Python 3.11+
- `python-telegram-bot`
- Gemini API via REST
- Notion API via REST
- Google Calendar API via service account
- Playwright untuk browsing halaman
- Reminder terjadwal kontekstual ke Telegram dengan fallback alarm webhook
- Dynamic nagging untuk tugas mendekati deadline
- Natural language input untuk bikin reminder/jadwal dari chat biasa
- Morning briefing harian ke Telegram jam 06:00
- Chain reminders Telegram setelah event tertentu selesai
- Daily auto-task list lokal untuk habit berulang seperti Duolingo dan Hack The Box

## Setup

1. Buat virtual environment dan install dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

2. Salin `.env.example` menjadi `.env`, lalu isi credential:

```bash
cp .env.example .env
```

3. Siapkan akses:

- Telegram: buat bot di BotFather dan ambil token
- Gemini: buat API key di Google AI Studio
- Notion: buat internal integration, share page target ke integration itu
- Google Calendar dan Google Docs: buat service account, aktifkan Google Calendar API dan Google Docs API, lalu share resource target ke email service account
- Reminder target chat: chat dulu ke bot lalu pakai command `/chat_id` untuk ambil `REMINDER_TELEGRAM_CHAT_ID`

Detail penting untuk Google Calendar:

- Jika memakai service account, jangan andalkan `GOOGLE_CALENDAR_ID=primary`
- Isi `GOOGLE_CALENDAR_ID` dengan email Gmail kalender target atau calendar ID yang persis dari Google Calendar settings
- Share kalender target itu ke email service account, minimal izin lihat event. Untuk membuat event, beri izin edit
- Setelah bot jalan, pakai command Telegram `/calendar_check` untuk validasi setup

Detail penting untuk Google Docs:

- Isi `GOOGLE_DOCS_DOCUMENT_ID` dengan document ID dari URL Google Docs kamu
- Share dokumen target itu langsung ke email service account
- Kalau bot cuma perlu baca, akses Viewer cukup. Kalau bot perlu append/replace isi dokumen, beri akses Editor
- Jika mau bot otomatis baca context di setiap turn dan menyimpan memory penting tanpa disuruh, biarkan `GOOGLE_DOCS_CONTEXT_AUTO_SYNC=true`
- Setelah bot jalan, pakai command Telegram `/docs_check` untuk validasi setup

Contoh URL:

```text
https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890/edit
```

Maka `GOOGLE_DOCS_DOCUMENT_ID` adalah:

```text
1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
```

## Menjalankan

```bash
python3 -m src.main
```

## Reminder Kontekstual

Bot bisa scan event Google Calendar yang mulai di menit berjalan, ambil konteks tambahan dari deskripsi event dan page Notion yang judulnya paling mirip, lalu kirim reminder dengan format:

```text
Udah jam [JAM] nih. Waktunya [NAMA_TUGAS]. [KONTEKS_TERAKHIR]. Target sekarang: [TARGET_SPESIFIK].
```

Env yang dipakai:

```bash
REMINDER_ENABLED=true
REMINDER_DELIVERY_CHANNEL=telegram
REMINDER_TELEGRAM_CHAT_ID=123456789
ALARM_WEBHOOK_URL=https://your-device.example/webhook
REMINDER_POLL_SECONDS=30
REMINDER_RESPONSE_TIMEOUT_MINUTES=10
```

Catatan implementasi:

- Trigger reminder sekarang berbasis start time event Google Calendar.
- Deskripsi event bisa diisi baris seperti `Konteks:` dan `Target:` untuk hasil yang lebih presisi.
- Jika Notion aktif, bot akan cari page yang judulnya paling mirip dengan nama task untuk ambil konteks tambahan.
- Jika dalam 10 menit belum ada balasan di chat Telegram yang sama, bot akan hit `ALARM_WEBHOOK_URL` lalu kirim pesan fallback satu kali.
- `WHATSAPP_WEBHOOK_URL` tersedia sebagai jalur kirim alternatif outbound, tapi deteksi respons otomatis saat ini tetap andal di Telegram karena bot ini memang menerima inbound dari Telegram.

## Dynamic Nagging

Bot juga bisa cek task yang belum selesai dan deadlinenya tinggal beberapa jam, lalu kirim prompt dua opsi:

```text
Kamu ada deadline [NAMA_TUGAS] jam [WAKTU_DEADLINE] nanti. Belum ada progres yang tercatat. Mau dikerjakan sekarang, atau aku ingetin lagi 30 menit lagi?
```

Setup env dasar:

```bash
DYNAMIC_NAGGING_ENABLED=true
DYNAMIC_NAGGING_SOURCE=auto
DYNAMIC_NAGGING_POLL_MINUTES=60
DYNAMIC_NAGGING_DEADLINE_WINDOW_HOURS=3
DYNAMIC_NAGGING_RESPONSE_TIMEOUT_MINUTES=10
DYNAMIC_NAGGING_MAX_REMINDERS=3
```

Provider yang didukung sekarang:

- Local task list bawaan di `var/task_list.json`. Ini dipakai juga buat auto-task harian seperti `Duolingo` dan `Hack The Box`.
- Notion database: isi `NOTION_TASK_DATABASE_ID` lalu map nama property title, status, deadline, dan progress sesuai database kamu.
- Todoist: isi `TODOIST_API_TOKEN`.
- Google Tasks: isi `GOOGLE_TASKS_TASKLIST_ID`, lalu pakai service account yang memang punya akses ke tasklist itu. Kalau perlu domain-wide delegation, isi juga `GOOGLE_TASKS_IMPERSONATE_USER`.

Perilaku nagging:

- Hanya task dengan status belum selesai dan deadline `<= 3 jam` yang akan dipertimbangkan.
- Fallback 10 menit tanpa respons akan kirim pesan kedua yang lebih urgent lalu hit `ALARM_WEBHOOK_URL`.
- Maksimal 3 reminder per task dalam state lokal bot.
- Balasan seperti `kerjain sekarang`, `ingetin lagi 30 menit`, atau `udah selesai` akan ditangkap dan dipakai buat follow-up otomatis.

## Daily Auto Task List

Bot sekarang bisa bikin task harian otomatis tanpa perlu diminta dulu. Default-nya setiap tanggal baru akan menambahkan:

- `Duolingo`
- `Hack The Box`

Task ini disimpan ke task list lokal di `var/task_list.json`, lalu otomatis ikut kebaca oleh `morning briefing` dan `dynamic nagging` kalau sumber task memakai mode `auto`.

Env tambahan:

```bash
DAILY_TASK_LIST_ENABLED=true
DAILY_TASK_TEMPLATES=Duolingo,Hack The Box
DAILY_TASK_DUE_HOUR=20
DAILY_TASK_DUE_MINUTE=0
LOCAL_TASK_STORE_FILE=var/task_list.json
```

Catatan:

- Pembuatan task dijaga idempoten, jadi `Duolingo` dan `Hack The Box` tidak akan dobel di hari yang sama.
- File task lokal otomatis dipangkas untuk item lama, jadi store-nya tidak terus membengkak.

## Natural Language Input

Bot juga bisa nangkep pesan santai yang isinya minta diingetin atau dijadwalin, lalu selalu minta konfirmasi sebelum nyimpen ke Google Calendar.

Contoh:

```text
Ingetin aku besok jam 3 sore buat baca jurnal RAG ya
Bikin event meeting skripsi besok jam 11-12
Tambahin ke kalender besok jam 11 sampai 12 untuk call client
```

Balasan bot:

```text
Oke, aku set: Meeting skripsi besok jam 11:00-12:00. Betul ya?
```

Kalau user jawab `iya`, bot akan bikin event Google Calendar. Event itu nanti ikut kebaca sama reminder kontekstual modul 01 saat waktunya tiba.

Env tambahan:

```bash
NATURAL_LANGUAGE_INPUT_ENABLED=true
CALENDAR_DEFAULT_EVENT_DURATION_MINUTES=30
```

## Google Docs Context Store

Bot sekarang bisa pakai satu Google Doc sebagai memory eksternal yang tahan restart, cocok buat preserve context jangka panjang.

Env tambahan:

```bash
GOOGLE_DOCS_DOCUMENT_ID=your_google_doc_id
GOOGLE_DOCS_CONTEXT_AUTO_SYNC=true
GOOGLE_DOCS_CONTEXT_MAX_CHARS=6000
```

Pola pakai yang didukung:

- baca isi dokumen untuk konteks lama
- append context baru ke bawah dokumen
- replace isi body dokumen kalau kamu memang mau reset total context
- auto-load context dari dokumen sebelum bot menjawab
- auto-append memory penting kalau user menyebut preferensi, prioritas, keputusan, constraint, atau proyek yang ongoing

Struktur dokumen yang direkomendasikan:

```text
Agent Context Store

Identity & Preferences
- bahasa utama: Indonesia santai
- kerja paling fokus malam hari

Current Priorities
- thesis bab 3
- cari internship ML

Open Loops
- belum pilih topik eksperimen final

Recent Decisions
- pakai Google Docs sebagai persistent memory utama

Memory Log
- [2026-05-26 10:15 Asia/Jakarta] priority: Fokus minggu ini thesis bab 3.
- [2026-05-26 10:16 Asia/Jakarta] preference: Lebih suka jawaban singkat, langsung ke inti.
```

Contoh chat:

```text
Baca context yang ada di Google Doc
Tambahin ke context store: tadi aku mutusin fokus minggu ini cuma ngerjain thesis bab 3
Ganti seluruh context doc dengan ringkasan terbaru ini: ...
```

Catatan:

- Implementasi saat ini fokus ke plain text body dokumen
- Kalau dokumennya sangat panjang, tool baca akan mengembalikan potongan awal dengan batas karakter
- Setup ini paling simpel kalau kamu pakai satu dokumen utama khusus memory agent
- Jika dokumen masih kosong dan auto-sync aktif, bot akan menginisialisasi template context store secara otomatis

Catatan:

- Parser sekarang cover pola waktu umum seperti `hari ini`, `besok`, `lusa`, nama hari, tanggal eksplisit, dan format `jam 3 sore` atau `15:30`.
- Range jam seperti `jam 11-12`, `11:00-12:00`, dan `11 sampai 12` sekarang dibaca sebagai start dan end time yang presisi.
- Kalau waktu belum cukup jelas, bot akan minta format yang lebih spesifik dulu dan belum menyimpan apa pun.
- Deskripsi event otomatis diisi `Konteks:` dan `Target:` kalau ada, supaya reminder modul 01 bisa pakai konteks itu.

## Morning Briefing

Karena setup sekarang memang Telegram-only dan bot-nya sudah jalan terus, briefing pagi dikirim langsung dari process bot yang sama ke chat Telegram target. Jadi nggak perlu nambah kanal lain atau cron terpisah.

Format pesannya dibuat ringkas maksimal 5 baris:

```text
Pagi! [SAPAAN_PERSONAL]. Hari ini [DESKRIPSI_SINGKAT_KEPADATAN].
Jadwal: [JAM EVENT] [NAMA EVENT] | ...
Prioritas tugas hari ini: [TUGAS DUE HARI INI]
Catatan: [INSIGHT / KONTEKS]
```

Env tambahan:

```bash
MORNING_BRIEFING_ENABLED=true
MORNING_BRIEFING_HOUR=6
MORNING_BRIEFING_MINUTE=0
MORNING_BRIEFING_PERSONAL_GREETING=semoga pagimu enak
```

Sumber data briefing:

- Google Calendar untuk semua event hari ini
- sumber to-do yang sudah kamu pakai di bot ini, lalu difilter yang due hari ini
- konteks personal ringan dari Notion kalau ada task atau event yang cocok

## Chain Reminders

Karena bot kamu sekarang Telegram-only, chain reminder ini juga dikirim langsung ke chat Telegram yang sama. Mekanismenya pakai polling Calendar, cek event yang baru selesai 2-5 menit lalu, terus cocokin ke rules yang kamu set.

Format pesannya:

```text
[NAMA_EVENT_SELESAI] udah beres kan? [AJAKAN_AKTIVITAS_BERIKUTNYA]. [ESTIMASI_WAKTU] aja cukup!
```

Env tambahan:

```bash
CHAIN_REMINDERS_ENABLED=true
CHAIN_REMINDER_POLL_SECONDS=60
CHAIN_REMINDER_DELAY_MIN_MINUTES=2
CHAIN_REMINDER_DELAY_MAX_MINUTES=5
CHAIN_REMINDER_RULES=[{"after":"Makan Malam","message":"Yuk buka laptop 1 jam buat review materi biar besok ga numpuk","estimate_minutes":"60"}]
```

Catatan:

- Rule dicocokkan terutama dari nama event Calendar `after`.
- Pengiriman dijaga satu kali per event instance.
- Kanal kirimnya tetap Telegram, jadi nggak ada jalur WhatsApp atau channel lain di modul ini.

## Menjalankan 24/7 di macOS

Project ini adalah bot Telegram polling. Di macOS, cara paling stabil untuk menjalankannya terus adalah `launchd`.

1. Pastikan dependency dan credential sudah siap:

```bash
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

2. Install service:

```bash
chmod +x scripts/*.sh
./scripts/install_launchd.sh
```

3. Cek status:

```bash
./scripts/status_launchd.sh
```

4. Restart setelah update kode atau env:

```bash
./scripts/restart_launchd.sh
```

5. Hapus service:

```bash
./scripts/uninstall_launchd.sh
```

Catatan operasi:

- `launchd` akan auto-start saat login dan auto-restart jika proses mati.
- Log service ada di `var/log/com.projectaiv1.telegram-bot.out.log` dan `var/log/com.projectaiv1.telegram-bot.err.log`.
- Ini bukan 24/7 sungguhan jika Mac tidur, mati, logout, atau kehilangan koneksi internet. Untuk always-on sebenarnya, pindahkan ke VPS atau host yang memang selalu hidup.

## Contoh chat

- "Cari catatan notion tentang roadmap Q3"
- "Buat page notion berjudul Meeting Notes dengan isi poin-poin ini..."
- "Lihat agenda saya besok"
- "Buat event besok jam 10 pagi bernama Sync Produk selama 30 menit"
- "Cari info terbaru tentang model Gemini lalu ringkas"

## Catatan

- Memory percakapan saat ini disimpan in-memory per chat.
- Tool browser melakukan search via DuckDuckGo HTML dan membuka halaman dengan Playwright.
- Untuk production, sebaiknya tambah persistence, auth layer, logging, dan rate limiting.
