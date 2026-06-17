# Public History — Implications & Guidance

## Apa itu Public History?

Public History adalah fitur yang memungkinkan halaman history evaluasi agent (`/history`) dan detail evaluasi (`/history/<run_id>`) diakses **tanpa autentikasi**. Ketika fitur ini diaktifkan, siapa pun yang mengetahui URL evonic Anda dapat melihat:

- Hasil evaluasi agent (skor, status test)
- Prompt dan response dari setiap test case
- Data evaluasi seperti query, expected answers, dan model responses
- Metadata run (model yang digunakan, durasi, jumlah token)

## Risiko Keamanan

Fitur ini bersifat **all-or-nothing**: jika diaktifkan, **semua** data evaluasi yang sudah ada maupun yang akan datang akan terekspos secara publik. Risiko yang perlu dipertimbangkan:

1. **Data sensitif dalam prompt**: Jika evaluasi menggunakan prompt yang mengandung informasi internal, rahasia bisnis, atau data pribadi, data tersebut akan bocor ke publik.
2. **Query pengguna**: Beberapa evaluasi mungkin berisi query nyata dari pengguna yang mengandung data sensitif.
3. **Model responses**: Response dari model AI mungkin berisi informasi yang tidak seharusnya dipublikasikan.
4. **Fingerprinting infrastruktur**: Metadata run dapat memberikan informasi tentang konfigurasi sistem Anda.

## Rekomendasi

1. **Nonaktifkan Public History** jika tidak benar-benar diperlukan.
2. **Audit data evaluasi** sebelum mengaktifkan fitur ini — pastikan tidak ada data sensitif dalam prompt, response, atau expected answers.
3. **Gunakan untuk demo/trial** — fitur ini cocok untuk lingkungan demo atau trial di mana data bersifat dummy/tidak sensitif.
4. **Monitor audit log** — perubahan pada pengaturan ini dicatat di audit log (`public_history` setting changes).
5. **Pertimbangkan akses read-only** — dengan public history aktif, pengguna yang tidak terautentikasi hanya bisa melihat data, tidak bisa menghapus atau mengubah.

## Cara Kerja Teknis

Ketika `public_history` diaktifkan (nilai `'1'` di database):
- Route `/history` dan `/history/<run_id>` di Flask akan melayani request tanpa login
- Route API `/api/run/<run_id>/matrix` dan endpoint terkait juga akan bisa diakses tanpa autentikasi
- Semua data evaluasi yang ada di database akan bisa dibaca oleh siapapun

Ketika dinonaktifkan (nilai `'0'`):
- Halaman history hanya bisa diakses oleh admin yang sudah login
- Endpoint API akan mengembalikan 401 Unauthorized untuk pengguna yang tidak terautentikasi
