# PRONAKER - Protokol Kemnaker RI

Aplikasi web resmi untuk Protokol Kementerian Ketenagakerjaan Republik Indonesia: **PRONAKER (Name Table & Note Pad Generator)**.

- **URL Utama**: [https://pronaker.vercel.app](https://pronaker.vercel.app) *(otomatis redirect ke `/nametable`)*
- **Name Table**: [https://pronaker.vercel.app/nametable](https://pronaker.vercel.app/nametable)
- **Note Pad**: [https://pronaker.vercel.app/notepad](https://pronaker.vercel.app/notepad) *(Segera Hadir)*

---

## Fitur Utama

1. **Live Preview Interaktif**:
   - Canvas HTML5 real-time dengan background resmi Kemnaker RI.
   - Pilihan font fleksibel (default: **Montserrat**, dengan opsi Myriad Pro, Roboto, EB Garamond, Open Sans, Plus Jakarta Sans).
   - Pengaturan ukuran font otomatis (*auto-fit*) atau manual dengan slider instan.
   - Jarak spasi baris presisi default 40 pt.

2. **Database Organisasi Kemnaker Terintegrasi**:
   - Mode beralih cepat antara **Tamu Eksternal** dan **Kemnaker RI**.
   - Autocomplete otomatis untuk Unit Utama (Sekretariat Jenderal, Ditjen Binwasnaker & K3, Ditjen Binalavotas, dll.) dan Pejabat/Jabatan.

3. **Cetak & Export Fleksibel**:
   - Single Card export langsung ke PDF print-ready (2 sisi: 1 tegak, 1 rotasi 180° untuk kartu meja).
   - Batch Generation via upload CSV dengan output ZIP siap unduh.
   - Multi-page PDF generation.

4. **Navigasi Responsif & Modern**:
   - Desktop: Top nav dengan active indicator underline bar presisi di tengah layar.
   - Mobile: Bento App Grid icon (⊞) dengan dropdown menu responsif dan notifikasi toast simetris.

---

## Persiapan & Menjalankan Lokal

```bash
# 1. Clone repository
git clone https://github.com/<username>/nametable-kemnaker.git
cd nametable-kemnaker

# 2. Setup Virtual Environment (opsional namun disarankan)
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # Linux/macOS

# 3. Install Dependencies
pip install -r requirements.txt

# 4. Jalankan Server
python app.py
```

Buka peramban di [http://localhost:5000](http://localhost:5000) (akan langsung diarahkan ke `/nametable`).
Atau di Windows, cukup klik ganda `start_nametag.bat`.

---

## Deployment ke Vercel

Proyek ini sudah dikonfigurasi secara optimal untuk serverless Python di Vercel:

- `vercel.json` mengarahkan semua rute dinamis ke `api/index.py`.
- `paths.output_dir()` otomatis mendeteksi environment `VERCEL` dan menggunakan direktori writable `/tmp/output`.
- Background template dan aset font dimuat langsung dari `static/`.
- Dependensi ringan tanpa headless browser yang berat, sehingga build dan deploy di Vercel selesai dalam hitungan detik.

### Langkah Deploy:
1. Hubungkan repository GitHub ke dashboard [Vercel](https://vercel.com).
2. Framework Preset: **Other** (Root directory: `./`).
3. Deploy! Vercel akan otomatis membaca `vercel.json` dan `requirements.txt`.
