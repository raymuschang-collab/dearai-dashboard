# Panduan Tim Produksi DearAI Studio
## Cara Pakai Claude Code untuk Produksi Microdrama

> **Untuk tim produksi DearAI** — producer, director, art director, editor, social team. Bukan untuk developer.
> Tujuan dokumen ini: kasih kalian satu tempat lihat semua "tombol" yang bisa dipakai di Claude Code, kapan harus pakai yang mana, dan kenapa.

---

## 📍 Bahasa: Bebas

**Kalian bisa ngetik di Claude pakai Bahasa Indonesia, English, atau campuran.**
Claude resolve maksudnya dari kata kerja + nomor set + @-mention. Yang penting alurnya jelas.

Contoh sah semuanya:
- *"vidgen set 9 V1"* (English)
- *"buat video set 9 V1"* (Bahasa)
- *"vidgen set 9 dengan @tara dan @minjun di @kitchen, dialognya pakai aksen Jakarta"* (campuran)

Body prompt yang masuk ke Seedance bisa dalam Bahasa juga — modelnya handle EN/ID/KO native.

---

## 🤔 Apa itu "/ command" (Slash Command)?

Bayangkan slash command seperti **tombol shortcut**. Daripada kalian harus copy-paste 20 baris instruksi setiap kali mau buat video, kalian cukup ketik:

```
/vidgen set 1 V1
```

Dan Claude tahu mau:
1. Buka sheet Storyboard Prompts
2. Baca body prompt dari row 11 kolom C
3. Auto-detect karakter, lokasi, prop yang muncul di body
4. Lookup kode asset BytePlus dari Asset Library tab
5. Susun prompt 600+ kata dengan globals, realism preamble, dialogue, microexpressions
6. Submit ke BytePlus Seedance 2 API
7. Polling tiap 30 detik sampai selesai
8. Download MP4
9. Upload ke folder Drive yang benar
10. Tulis URL kembali ke sheet

**Kalian cuma ketik 4 kata. Claude lakuin 10 langkah.**

---

## 🎯 Kenapa Pakai / command?

| Tanpa / command | Dengan / command |
|---|---|
| Copy-paste prompt panjang dari template | Ketik 4 kata |
| Salah ketik kode asset BytePlus → moderation flag → reject | `@tara` resolve otomatis dari Asset Library |
| Lupa attach storyboard ref → output ngawur | Auto-attach iter yang benar |
| Hardcode resolusi, aspect, duration tiap kali | Default sudah benar, override pakai flag |
| Tiap orang di tim hasilnya beda | Semua orang dapet alur yang sama persis |
| Susah debug kalau error | Output log ada lokasinya tetap |

**Inti pesan:** / command itu **konsistensi + kecepatan**. Tim 8 orang, semua dapat hasil yang sama, semua selesai 10x lebih cepat dibanding manual.

---

## 🔗 Sistem @ — Magic Sebenarnya

`@` itu cara kalian referensikan **asset apapun** di Asset Library tanpa hafal kode-nya.

```
@tara         → TARA ANJANI (pulls image + video + audio assets)
@minjun       → PARK MIN-JUN (image + video + voice)
@kitchen      → INT. Kitchen 4 (Hanbyeol Bistro Kitchen)
@bibimbap     → Bibimbap bowl
@cigarette    → Cigarette
@logo         → Hanbyeol Logo
```

**Cara kerjanya:**
1. Kalian ketik `@tara` di prompt
2. Claude buka tab "Asset Library" di bible sheet
3. Cari nama "TARA ANJANI"
4. Ambil semua kode BytePlus yang related (image, video, audio)
5. Attach ke API call

**Pentingnya:**
- Kalau asset lama di-replace di BytePlus, kode lama mati → kalian gak perlu update di mana-mana → cukup update Asset Library tab → prompt pakai `@tara` tetap jalan
- Tim non-tech gak perlu hafal kode `sx786` `ckwpd` `5vhnf` — cukup `@tara`
- Kalau ada karakter/lokasi/prop baru, tinggal tambah row di Asset Library, semua / command langsung bisa pakai

> 💡 **Aturan emas:** Asset Library tab adalah *single source of truth*. Update sekali, dipakai di mana-mana.

---

## 📋 Daftar / command Produksi

### 🎬 Pembuatan Konten

| Command | Apa fungsinya | Kapan dipakai |
|---|---|---|
| `/shotlist-gen` | Atomize script jadi shotlist + isi 5 bible (text-only) | Saat scriptnya baru dikasih, mau mulai produksi episode baru |
| `/imggen` | Generate storyboard untuk satu set | Mau preview satu adegan dulu, atau regen yang gagal |
| `/imggen-all-storyboards` | Generate semua storyboard untuk satu episode | Setelah shotlist final, sebelum vidgen |
| `/imggen-all-assets` | Generate semua referensi karakter/lokasi/prop/effect | Awal produksi, sebelum upload ke BytePlus |
| `/vidgen` | Generate satu video pakai Seedance 2 | Per-set vidgen, fleksibel banget |
| `/vidgen-all-sets` | Generate semua video di episode | Setelah storyboards approved, fire all |
| `/episode-assemble` | Cut all videos jadi satu MP4 final | Step terakhir, gabung jadi episode utuh |
| `/episode-pipeline` | Tombol merah besar — semua step dari script ke episode jadi | Sekali jadi semua, dari nol sampai master file |

### 🔧 Asset Management

| Command | Apa fungsinya | Kapan dipakai |
|---|---|---|
| `/byteplus-upload-all` | Upload semua bible assets ke BytePlus | Setelah `/imggen-all-assets` selesai |
| `/byteplus-flush` | Hapus asset BytePlus yang sudah Replaced | Saat asset library berantakan, mau bersih-bersih |
| `/validate-asset-library` | Cek tiap row Asset Library masih valid di BytePlus | Sebelum sesi vidgen besar, untuk pastiin tidak ada orphan |
| `/byteplus-balance` | Cek kredit BytePlus | Sebelum fire massal |
| `/byteplus-expense` | Total spending per show | Untuk laporan budget |

### ✏️ Editing

| Command | Apa fungsinya | Kapan dipakai |
|---|---|---|
| `/shotlist-edit` | Edit cell, insert/delete row di shotlist | Revisi minor pada shotlist locked |

---

## 💡 Fleksibilitas — Inilah Kekuatan Sebenarnya

Setiap / command punya **mode default yang aman** dan **flag untuk override**. Tim bisa mulai dari default; expert bisa tweak via flag.

### `/vidgen` punya **4 mode**

```
1. LOCKED    — pakai shotlist apa adanya
   /vidgen set 1 V1

2. HYBRID    — body shotlist tapi ganti referensi
   /vidgen set 1 referensi @tara @galih @alley
   /vidgen set 1 dengan @tara saja

3. FREEFORM  — body bebas, referensi bebas
   /vidgen @tara plating bibimbap di @kitchen, dialognya: "Aku tidak tahu lagi."
   /vidgen buat video @tara berjalan di @alley malam hari, 480p 8s

4. RAW       — paste prompt full, edit bebas, tinggal tag @-nya saja
   (klik "copy full prompt" di gallery → paste di Claude → edit → "fire as-is")
```

**Flag ekstra:**
- `--resolution 480p|720p|1080p` (default 480p; pakai 720p/1080p untuk hero deliverables)
- `--duration 4-15` (detik, default 15)
- `--aspect 9:16|16:9` (default 9:16 vertical, untuk preview deck pakai 16:9)
- `--confirm` (tampilkan prompt dulu, baru fire — pakai untuk run mahal)
- `--mentions @tara @minjun` (override manual; hanya referensi yang disebut yang dipakai)

Output video juga disimpan lokal otomatis di:
`~/Desktop/<Project> Generated Videos/`

Contoh override manual:
```
/vidgen sheet --set 1 --slot 1                        → auto-detect
/vidgen sheet --set 1 --slot 1 @tara @minjun @kitchen → hanya 3 referensi ini
/vidgen sheet --set 1 --slot 1 @galih                 → hanya Galih
```

### Routing provider image/video

| Kebutuhan | Provider |
|---|---|
| Storyboard | Higgsfield `gpt_image_2` |
| Character refs | Higgsfield `gpt_image_2` |
| Costume / props / effects | Higgsfield `nano_banana_2` |
| Location refs | Reve direct, bukan Higgsfield |
| Vidgen live-action | BytePlus Seedance |

### `/imggen` punya **4 aesthetic mode**

```
--stick      (DEFAULT — gak perlu ketik) Stick figure TANPA wajah, blocking-only.
                                          Style sajangnim. PALING MURAH.
                                          Preamble di-FORCE oleh script — sheet
                                          globals di-override otomatis. Aman.

--pencil     Pencil sketch director-pad. Features readable tapi loose.
                                          Untuk shot review yang butuh fidelity
                                          lebih tinggi dari stick.

--photoreal  Full photoreal stills (Arri Alexa 35, Kodak Vision3 250D).
                                          MAHAL. Pakai HANYA untuk hero
                                          deliverable, bukan coverage validation.

--sheet      LEGACY. Pakai apapun yang ada di B1:B4 globals sheet.
                                          Cuma pakai kalau tahu persis kenapa
                                          dibutuhkan. Default-nya jangan disentuh.
```

**Contoh:**
```
/imggen sheet-id set 4                    # default stick figures
/imggen sheet-id set 4 --pencil           # pencil sketch
/imggen sheet-id set 4 --photoreal        # photoreal (mahal!)
/imggen sheet-id                          # semua Pending sets, stick figures
/imggen-all-storyboards --sheet sheet-id  # bulk semua, stick figures
```

> 💡 **Aturan emas:** Default = stick figures untuk SEMUA produksi normal. Storyboard itu **alat coverage validation** — yang penting blocking + camera + staging. Bukan likeness, bukan lighting, bukan wardrobe. Kalau stakeholder masih debat likeness di stage storyboard, jawabannya bukan ship photoreal storyboard — tapi lock cast bible dulu sebelum storyboards.

### `/imggen-all-assets` selektif

```
--bibles characters,locations         → cuma 2 bible itu
--bibles props,costume,effects        → cuma 3 bible itu
(tanpa flag → semua 5 bible)
```

### `/episode-pipeline` step-skip

```
--from-step 3                         → mulai dari step 3 (skip script + asset gen)
--to-step 5                           → stop setelah step 5 (skip vidgen + assemble)
--skip 4,5                            → loncat step 4 dan 5 saja
```

> 💡 **Tips:** Default itu sudah benar untuk 80% kasus. Flag dipakai cuma kalau perlu override. Kalau ragu, jangan pakai flag.

---

## 🏗️ Workflow Standar

### Workflow A — Script ke Episode Jadi (semua otomatis)

```
1. Tim creative kasih script (.txt atau .docx)
2. Buka Claude Code
3. Ketik:
   /episode-pipeline --sheet 1abc... --script /path/script.txt
4. Tunggu ~2 jam
5. Episode MP4 keluar di Drive folder
```

**Cocok untuk:** episode standar, tidak ada twist khusus, tim percaya output AI

### Workflow B — Step-by-step (kontrol penuh)

```
1. /shotlist-gen --script ...        ~5 menit
2. (Producer review shotlist + bibles, edit kalau perlu)
3. /imggen-all-assets                ~30 menit
4. /byteplus-upload-all              ~10 menit
5. /imggen-all-storyboards           ~25 menit
6. (Director pilih iter 1 atau iter 2 per set di gallery)
7. /vidgen-all-sets                  ~45 menit
8. (Tim review videos, fire ulang yang gagal)
9. /episode-assemble                 ~5 menit
```

**Cocok untuk:** episode hero, budget high, butuh review tiap step

### Workflow C — Quick fire untuk test

```
/vidgen @tara berjalan di @alley malam, 480p 8s
```

**Cocok untuk:** test ide baru, prototype scene, casting check

### Workflow D — Revisi minor

```
/imggen set 5 --force          (regen storyboard set 5)
/vidgen set 9 V2                (re-fire iter 2 set 9)
/shotlist-edit set 7 dialogue: "TARA: Aku sudah tahu sejak lama."
```

**Cocok untuk:** patch kecil setelah review director

---

## 🎓 Tips & Aturan Praktis

### ✅ Yang sebaiknya dilakukan

- **Selalu mulai dari Asset Library** — pastikan semua karakter/lokasi sudah ada di sana sebelum fire vidgen
- **Pakai resolusi 480p untuk testing** — 1080p 2.6x lebih mahal, simpan untuk hero shot
- **Test 1 set dulu sebelum fire all** — `/vidgen set 1 V1` sebelum `/vidgen-all-sets`
- **Pakai bahasa apapun di body** — Seedance handle Bahasa, English, Korean
- **Update Asset Library, jangan hardcode kode di prompt** — kalau pakai `@tara` semua tetap jalan walau kode berubah

### ❌ Yang harus dihindari

- **Jangan delete asset di BytePlus tanpa update Asset Library** — vidgen akan error karena referensi kosong
- **Jangan fire 1080p tanpa `--confirm`** — mahal, harus preview dulu
- **Jangan re-fire job yang gagal tanpa cek alasan** — biasanya ada alasan jelas (budget bust, rate limit, asset stale)
- **Jangan modify bible tabs tanpa konfirmasi tim** — bible adalah source of truth bersama
- **Jangan share kunci API BytePlus** — semua kunci di `.env`, jangan paste di chat / Slack / Discord

### 🚨 Kalau / command Error

1. **Baca pesan error dulu** — biasanya jelas kenapa
2. **Kalau "rate limit"** — tunggu 1 menit, coba lagi
3. **Kalau "asset not found"** — cek Asset Library, mungkin row stale
4. **Kalau "moderation flag"** — body prompt mungkin terlalu spesifik, generalisasi sedikit
5. **Kalau "credits exhausted"** — contact admin untuk top-up
6. **Kalau bingung** — screenshot error + tag di Discord/Slack

---

## 🆘 FAQ

**Q: Saya bukan developer. Apakah saya perlu install sesuatu?**
A: Setup awal install Claude Code (panduan terpisah di TEAM_CLAUDE_SETUP.md). Setelah itu, kalian cuma ketik di Claude — gak perlu coding.

**Q: Apakah / command bisa saya custom?**
A: Bisa minta tim teknis tambah / command baru. Tapi 7 / command yang ada sudah cover 95% workflow produksi.

**Q: Apakah saya bisa pakai dari handphone?**
A: Bisa via Claude mobile app + remote terminal, tapi disarankan pakai laptop untuk run yang lama (>10 menit).

**Q: Bagaimana kalau saya mau coba mode di luar default?**
A: Kasih flag, contoh `--resolution 1080p` atau `--photoreal`. Lihat tabel "Fleksibilitas" di atas.

**Q: Bagaimana kalau Claude lupa cara kerja / command?**
A: Ketik *"baca CLAUDE.md"* — Claude akan re-load. CLAUDE.md di repo root adalah memory persistent.

**Q: Berapa lama tipikal episode jadi?**
A: ~2 jam dari script ke MP4, dengan / episode-pipeline. Dengan workflow B (step-by-step + review), sekitar 4-5 jam termasuk review.

**Q: Kalau saya mau bikin animation/mograph, apakah / command bisa?**
A: Untuk mograph yang structured (text reveal, transition, kinetic typography), lebih baik pakai Remotion / After Effects. / vidgen Seedance bagusnya untuk live-action. Mograph JSON template sudah ada di repo (`edb_c02_mograph.json`) sebagai contoh struktur.

**Q: Apakah saya bisa lihat semua / command yang ada?**
A: Di Claude Code, ketik `/` saja → list semua / command muncul. Atau buka file `CLAUDE.md` di repo root.

---

## 📂 File Penting yang Wajib Tahu

| File | Fungsi |
|---|---|
| `CLAUDE.md` | Memory persistent — Claude baca otomatis tiap sesi |
| `TEAM_CLAUDE_SETUP.md` | Panduan setup Claude Code di laptop kalian |
| `TEAM_BYTEPLUS_VIDGEN.md` | Detail teknis BytePlus API (untuk yang penasaran) |
| `PANDUAN_TIM_PRODUCTION.md` | File ini — referensi cepat untuk tim |
| `.env` | Kunci API (jangan share, jangan commit ke git) |
| Asset Library tab di bible sheet | Source of truth untuk @-mention |

---

## 🚀 Next Steps untuk Tim Baru

1. **Hari 1** — Setup Claude Code (ikuti `TEAM_CLAUDE_SETUP.md`)
2. **Hari 1** — Baca file ini sampai habis (15 menit)
3. **Hari 1** — Coba `/vidgen @tara berjalan di @alley, 480p 4s` (test cepat)
4. **Hari 2** — Coba workflow B step-by-step di EP02
5. **Hari 3 onwards** — Pakai workflow A (`/episode-pipeline`) untuk episode produksi

---

## 💬 Pertanyaan & Bantuan

- Pertanyaan teknis / error: **#dev-help** di Discord
- Pertanyaan workflow / produksi: **#production** di Discord
- Bug report: tag tim teknis dengan screenshot

**Yang paling penting:** kalau ragu, *jangan tebak*. Tanya. / command itu cepat tapi kalau dipakai salah bisa overwrite kerjaan tim.

---

*Last updated: 2026-05-09 · DearAI Studio Production Team*
