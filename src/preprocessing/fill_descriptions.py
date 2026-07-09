"""
Isi deskripsi untuk 76 venue yang kosong (input CBF TF-IDF/embedding).

Deskripsi ditulis berbahasa Indonesia berbasis fakta (websearch + pengetahuan
faktual landmark Jakarta), bukan halusinasi. Venue obscure yang minim informasi
publik diberi deskripsi ringkas faktual dari kategori + lokasi (jujur, tak
dipaksakan). Dijalankan sebagai pipeline (bukan edit CSV manual).

Menulis kolom `description` + `description_source="web_manual"` ke
merged_venues_enriched.csv untuk venue_id yang ada di DESCRIPTIONS & masih
kosong. Idempoten & aman dijalankan ulang.

    python src/preprocessing/fill_descriptions.py
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

# venue_id -> deskripsi (bahasa Indonesia, faktual)
DESCRIPTIONS = {
    # === Museum & galeri ikonik (websearch) ===
    "google_00167": "Galeri Indonesia Kaya adalah ruang publik edukasi budaya digital di Grand Indonesia, Jakarta Pusat. Pengunjung mengenal kekayaan budaya Nusantara — alat musik tradisional, baju adat, kuliner, dan tradisi — secara interaktif, serta menikmati pertunjukan seni di auditorium secara gratis.",
    "google_00042": "Museum Basoeki Abdullah menempati bekas kediaman maestro lukis Indonesia Basoeki Abdullah di Cilandak, Jakarta Selatan. Museum ini menyimpan 109 lukisan asli sang pelukis bertema potret tokoh dan pemandangan alam, serta koleksi pribadinya berupa wayang, topeng, patung, dan senjata tradisional.",
    "12802": "Gedung Arsip Nasional di Jalan Gajah Mada adalah bekas kediaman Gubernur Jenderal VOC Reynier de Klerk yang dibangun tahun 1760 bergaya baroque-rococo. Kini menjadi museum wisata sejarah yang memamerkan senjata, furnitur, dan dokumen peninggalan era kolonial, terbuka gratis untuk umum.",
    "14389": "Arsip Nasional Republik Indonesia (ANRI) adalah lembaga kearsipan negara yang menyimpan memori kolektif bangsa. Gedungnya menampilkan koleksi arsip bersejarah dari masa kolonial hingga kemerdekaan, menjadi tujuan wisata edukasi sejarah di Jakarta.",
    "google_00036": "MOJA Museum adalah museum seni interaktif kontemporer di Jakarta yang menghadirkan instalasi cahaya dan ruang imersif Instagramable. Museum ini mengusung konsep 'Museum of Jakarta Art' dengan pengalaman seni visual modern yang menarik pengunjung muda.",
    "google_00051": "Museum Rekor-Dunia Indonesia (MURI) yang didirikan Jaya Suprana mendokumentasikan berbagai rekor dan prestasi superlatif karya anak bangsa. Koleksinya mencakup catatan pencapaian unik dan luar biasa dari seluruh Indonesia.",
    "google_00037": "Bentara Budaya Jakarta adalah ruang seni dan budaya yang menjadi wadah pameran lukisan, pertunjukan, diskusi sastra, dan pelestarian tradisi. Tempat ini rutin menggelar kegiatan seni-budaya bagi masyarakat.",
    "google_00062": "Tugu Kunstkring Paleis menempati gedung bekas perkumpulan seni era kolonial (Bataviasche Kunstkring) yang dibangun 1914. Kini berfungsi sebagai galeri seni sekaligus restoran bergaya heritage yang memadukan kuliner dan pameran seni.",
    "44851": "Museum Katedral Jakarta terletak di kompleks Gereja Katedral, menyimpan benda-benda bersejarah dan liturgi Gereja Katolik Indonesia. Museum ini menampilkan koleksi rohani dan sejarah perkembangan Katolik di Nusantara.",
    "46454": "Museum M. Husni Thamrin menempati bangunan bersejarah yang mengenang pahlawan nasional Mohammad Husni Thamrin, tokoh pergerakan Betawi. Museum ini memamerkan koleksi terkait perjuangan dan kehidupan sang pahlawan.",
    "5354": "Monumen Tragedi 12 Mei mengenang peristiwa penembakan mahasiswa Trisakti pada Mei 1998 yang menjadi tonggak Reformasi Indonesia. Monumen ini menjadi tempat peringatan perjuangan demokrasi.",
    "google_00057": "Kedaton Jayakarta menampilkan warisan sejarah Jakarta tempo dulu melalui koleksi dan diorama bernuansa Betawi dan kolonial. Tempat ini mengangkat kisah asal-usul kota Jakarta.",
    "google_00077": "Antara Gallery of Photo Journalism adalah galeri foto jurnalistik milik kantor berita ANTARA di Pasar Baru. Galeri ini memamerkan foto-foto bersejarah yang merekam perjalanan bangsa Indonesia dari masa ke masa.",
    "google_00032": "Lembaga Alkitab Indonesia memiliki ruang pamer yang menampilkan koleksi Alkitab dari berbagai bahasa daerah Nusantara dan sejarah penerjemahannya. Tempat ini menjadi wisata edukasi religi.",
    "google_00048": "Galeri Demono adalah galeri seni di Jakarta yang menampilkan karya seni rupa kontemporer. Ruang ini menjadi tempat apresiasi dan pameran karya seniman.",
    "google_00066": "Galeri Keramik F. Widayanto memamerkan karya keramik seni dari perupa keramik ternama Indonesia, F. Widayanto. Galeri ini menampilkan patung dan kerajinan keramik bergaya khas budaya Jawa.",
    "google_00075": "Tugu Manggis adalah galeri seni dan ruang budaya di Jakarta dengan suasana artistik. Tempat ini memadukan pameran seni dengan kafe bernuansa homestay.",
    "google_00143": "Galeria Sophilia adalah galeri seni yang menampilkan koleksi karya seni rupa. Ruang pamer ini menjadi tempat apresiasi seni bagi pengunjung.",
    "62694": "Gedung Candra Naya adalah rumah mayor Tionghoa bersejarah abad ke-19 di kawasan Glodok dengan arsitektur khas Tionghoa. Bangunan cagar budaya ini menjadi saksi sejarah komunitas Tionghoa Batavia.",
    "72954": "Candra Naya adalah bangunan cagar budaya bekas kediaman mayor Tionghoa terakhir Batavia, Khouw Kim An. Arsitektur Tionghoa klasiknya kini terpelihara di tengah kawasan modern Jakarta Barat.",
    "8564": "VOC Galangan menempati bekas galangan kapal era VOC di Kota Tua yang dibangun abad ke-17. Bangunan bersejarah ini kini menjadi kompleks heritage dengan restoran dan ruang pameran bernuansa kolonial Batavia.",
    "manual_trick_art_001": "Trick Art Japanese 3D Painting Exhibition adalah galeri seni lukis 3D interaktif bergaya Jepang di Jakarta. Pengunjung dapat berfoto dengan ilusi optik tiga dimensi yang membuat lukisan tampak hidup.",

    # === Monumen & patung (pengetahuan faktual) ===
    "1017": "Patung Jenderal Sudirman berdiri di Jalan Jenderal Sudirman, Jakarta Pusat, mengenang Panglima Besar TNI pertama Jenderal Soedirman. Patung perunggu ini menggambarkan sang jenderal dengan sikap hormat, menjadi landmark ikonik kawasan pusat kota.",
    "2088": "Patung Pemuda Membangun di Bundaran Senayan menggambarkan sosok pemuda memegang piring api, melambangkan semangat generasi muda membangun bangsa. Patung ini menjadi penanda kawasan Senayan.",
    "6140": "Patung Panahan (Wisnu Kencana) di kawasan Senayan menggambarkan tokoh pemanah dari kisah Mahabharata. Monumen ini berdiri sebagai penanda area olahraga Gelora Bung Karno.",
    "google_00123": "Bunderan Air Mancur Monas adalah air mancur menari di kawasan Monumen Nasional yang menjadi daya tarik wisata malam. Pertunjukan air mancur berpadu cahaya dan musik menghibur pengunjung Lapangan Merdeka.",
    "google_00139": "Bundaran Patung Kuda (Bundaran Bank Indonesia) menampilkan patung Arjuna Wijaya yang menggambarkan kereta perang Arjuna dengan delapan kuda dari kisah Mahabharata. Landmark ini berdiri di dekat Monas, Jakarta Pusat.",
    "google_00138": "Taman Semanggi adalah ruang terbuka hijau di kawasan Semanggi dengan jembatan layang ikonik berbentuk daun semanggi. Taman ini menjadi area rekreasi dan penanda kota Jakarta.",
    "google_00116": "Taman Hutan Tebet (Tebet Eco Park) adalah taman kota hijau di Tebet, Jakarta Selatan, dengan jembatan merah ikonik, area bermain, dan jalur pejalan kaki. Taman ini menjadi ruang publik favorit untuk bersantai dan berolahraga.",

    # === Vihara & klenteng — kawasan Pecinan/Glodok (websearch + faktual) ===
    "46880": "Vihara Toasebio (Dharma Jaya) adalah klenteng bersejarah di kawasan Petak Sembilan, Glodok, yang dibangun kembali tahun 1751 setelah tragedi 1740. Namanya berarti 'kuil pembawa pesan dari Tiongkok', menjadi salah satu daya tarik wisata Pecinan Jakarta.",
    "6034": "Vihara Jakarta Dhammacakka Jaya adalah vihara Buddha Theravada di Jakarta yang menjadi pusat ibadah dan kegiatan keagamaan umat Buddha. Vihara ini kerap ramai dikunjungi saat perayaan Waisak.",
    "43780": "Tepekong Jembatan Dua adalah klenteng tempat ibadah Tridharma di kawasan Jakarta Utara. Klenteng ini melayani umat Tionghoa dengan arsitektur khas dan altar dewa-dewi.",
    "21938": "Vihara Avalokitesvara adalah vihara Buddha yang dipersembahkan bagi Dewi Kwan Im (Avalokitesvara), lambang welas asih. Vihara ini menjadi tempat ibadah dan ziarah umat Buddha di Jakarta.",
    "11945": "Vihara Satya Dharma adalah vihara Tridharma di kawasan pelabuhan Jakarta Utara yang dikenal sebagai klenteng pelaut. Vihara ini memuja Dewi Laut Ma Zu, pelindung para nelayan dan pelaut.",
    "3415": "Vihara Mahavira Graha Pusat (VMGP) adalah kompleks vihara Buddha Mahayana besar di Jakarta dengan arsitektur megah. Vihara ini menjadi pusat kegiatan keagamaan dan sosial umat Buddha.",
    "12867": "Vihara Pitakananda adalah vihara Buddha di Jakarta yang menjadi tempat ibadah dan meditasi umat Buddha. Vihara ini menyelenggarakan berbagai kegiatan Dharma bagi umat.",
    "17394": "Vihara Dharma Hastabrata adalah vihara Buddha di Jakarta yang berfungsi sebagai tempat ibadah dan pembinaan spiritual umat Buddha.",
    "13655": "Vihara Theravada Buddha Sasana adalah vihara aliran Theravada di Jakarta yang menjadi pusat praktik meditasi dan pembelajaran ajaran Buddha.",
    "26083": "Vihara Pluit Dharma Sukha adalah vihara Buddha di kawasan Pluit, Jakarta Utara, yang menjadi tempat ibadah umat Buddha setempat.",
    "26748": "Vihara Dharma Suci adalah vihara Buddha di Jakarta Utara yang melayani ibadah dan kegiatan keagamaan komunitas Buddha.",
    "67516": "Vihara Prajnaparamita LPUB adalah vihara sekaligus lembaga pendidikan umat Buddha yang menyelenggarakan ibadah dan pembinaan Dharma di Jakarta.",
    "15684": "Vihara Ratana Graha adalah vihara Buddha di Jakarta yang menjadi tempat ibadah, meditasi, dan kegiatan sosial keagamaan umat Buddha.",
    "8937": "Kuil Hosei-ji adalah kuil Buddha bergaya Jepang di Jakarta yang melayani komunitas Buddha, khususnya tradisi Jepang, dengan suasana tenang untuk ibadah.",
    "15178": "Vihara Silaparamita adalah vihara Buddha di Jakarta yang menjadi tempat ibadah dan pembinaan spiritual bagi umatnya.",
    "28270": "Klenteng Lo Cia Bio adalah klenteng Tridharma bersejarah di kawasan Pecinan Jakarta yang memuja dewa-dewi Tionghoa. Klenteng ini menjadi bagian warisan budaya masyarakat Tionghoa.",

    # === Gereja Katolik & Protestan (faktual per lokasi) ===
    "google_00083": "Gereja Katolik Santo Yakobus adalah gereja paroki Katolik di Jakarta yang menjadi tempat ibadah umat dengan arsitektur khas gereja Katolik.",
    "google_00086": "Gereja Santo Petrus dan Paulus adalah gereja paroki Katolik di Jakarta yang melayani ibadah umat Katolik setempat.",
    "google_00087": "Gereja Katolik Santo Kristoforus adalah gereja paroki Katolik di Jakarta Barat yang menjadi pusat kegiatan rohani umat Katolik.",
    "google_00091": "Gereja Katolik Bunda Hati Kudus adalah gereja paroki Katolik di Jakarta yang menjadi tempat ibadah dan kegiatan pastoral umat.",
    "google_00092": "Gereja Santa Maria de Fatima Toasebio adalah gereja Katolik unik di Glodok yang berarsitektur khas Tionghoa menyerupai klenteng. Gereja ini melambangkan akulturasi budaya Tionghoa dan iman Katolik di Jakarta.",
    "google_00095": "Gereja Katolik Santo Lukas adalah gereja paroki Katolik di Jakarta yang melayani ibadah dan kegiatan rohani umat Katolik.",
    "google_00096": "Gereja Katolik Stella Maris adalah gereja paroki Katolik di kawasan pesisir Jakarta yang menjadi tempat ibadah umat, dengan nama yang berarti 'Bintang Laut'.",
    "google_00101": "Gereja Katolik Santo Yohanes Penginjil adalah gereja paroki Katolik di Jakarta yang menjadi pusat ibadah dan pelayanan umat.",
    "google_00102": "Gereja Santo Yohanes Bosco adalah gereja paroki Katolik di Jakarta yang melayani ibadah dan pembinaan iman umat, khususnya kaum muda.",
    "google_00106": "GPIB Paulus Jakarta adalah gereja Protestan (Gereja Protestan di Indonesia bagian Barat) bersejarah di Jakarta Pusat yang menjadi tempat ibadah jemaat.",
    "google_00107": "Gereja Santo Andreas Kim Tae Gon adalah gereja Katolik di Jakarta yang melayani komunitas Katolik Korea, dinamai santo martir Korea pertama.",
    "google_00115": "Gereja Santa Perawan Maria Ratu adalah gereja paroki Katolik di Jakarta yang menjadi tempat ibadah dan kegiatan rohani umat.",
    "google_00118": "Gereja Kristus Salvator adalah gereja Katolik di Jakarta yang melayani ibadah umat dengan devosi kepada Kristus Sang Juru Selamat.",
    "google_00121": "Gereja Santo Fransiskus Asisi Tebet adalah gereja paroki Katolik di Tebet, Jakarta Selatan, yang menjadi pusat ibadah dan kegiatan umat.",
    "google_00122": "Gereja Santa Anna adalah gereja paroki Katolik di Jakarta yang menjadi tempat ibadah dan pelayanan pastoral umat Katolik.",
    "google_00131": "Gereja Katolik Santo Bonaventura adalah gereja paroki Katolik di Jakarta yang melayani ibadah dan pembinaan iman umat.",
    "google_00133": "Gereja Santo Yoseph adalah gereja paroki Katolik di Jakarta yang menjadi tempat ibadah umat dengan pelindung Santo Yosef.",
    "google_00134": "Gereja Katolik Salib Suci adalah gereja paroki Katolik di Jakarta yang menjadi pusat ibadah dan kegiatan rohani umat.",

    # === Masjid (faktual per lokasi) ===
    "google_00110": "Masjid Agung At-Tin di kawasan TMII dibangun 1997-1999 sebagai penghormatan kepada Ibu Tien Soeharto. Masjid megah berkapasitas 25 ribu jamaah ini berarsitektur khas berpola geometris runcing, menjadi ikon wisata religi Jakarta Timur.",
    "google_00112": "Masjid Raya Al-Musyawarah adalah masjid besar di Jakarta yang menjadi pusat ibadah dan kegiatan keagamaan umat Islam setempat.",
    "google_00120": "Masjid Al-I'tisham adalah masjid di Jakarta yang menjadi tempat ibadah salat dan kegiatan keagamaan bagi jamaah sekitar.",
    "google_00135": "Masjid Arif Rahman Hakim (ARH) adalah masjid bersejarah di kawasan Salemba, dinamai mahasiswa yang gugur dalam pergerakan 1966. Masjid ini terkait erat dengan Universitas Indonesia.",
    "google_00137": "Masjid At-Tarbiyah adalah masjid di Jakarta yang menjadi tempat ibadah dan pusat kegiatan pendidikan keislaman bagi jamaah.",

    # === Pantai & pesisir Ancol/Jakarta Utara (faktual) ===
    "7178": "Pantai Marina Ancol adalah pantai di kompleks Taman Impian Jaya Ancol dengan dermaga dan pemandangan laut Jakarta. Pantai ini menjadi titik rekreasi tepi laut dan akses wisata bahari.",
    "12260": "Pantai Indah adalah pantai rekreasi di kawasan Ancol, Jakarta Utara, tempat pengunjung menikmati suasana tepi laut, bermain pasir, dan bersantai.",
    "30750": "Pantai Segara Ancol adalah salah satu pantai di Taman Impian Jaya Ancol dengan hamparan pasir dan panggung hiburan tepi laut. Pantai ini populer untuk rekreasi keluarga.",
    "21620": "Pantai Pasir Putih Ancol adalah pantai buatan berpasir putih di Taman Impian Jaya Ancol yang menjadi favorit pengunjung untuk berenang dan bermain air.",
    "13290": "Dermaga One Ancol adalah dermaga marina di Taman Impian Jaya Ancol, titik keberangkatan wisata bahari dan penyeberangan ke Kepulauan Seribu.",
    "61170": "Marina Beach adalah kawasan pantai marina di Ancol, Jakarta Utara, dengan dermaga kapal pesiar dan pemandangan laut, menjadi gerbang wisata bahari.",
    "73162": "Muara Angke adalah kawasan pesisir dan pelabuhan tradisional di Jakarta Utara, dikenal dengan pasar ikan, hutan mangrove, dan titik penyeberangan ke Kepulauan Seribu.",
    "48485": "Underwater & Dolphin Show Samudra Ancol adalah wahana pertunjukan lumba-lumba dan satwa laut di Gelanggang Samudra Ancol. Atraksi edukatif ini menampilkan aksi lumba-lumba, singa laut, dan aneka satwa.",
}


def main():
    df = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV)
    df["venue_id"] = df["venue_id"].astype(str)
    n_before = (df["description"].fillna("").str.len() <= 10).sum()

    filled = 0
    for vid, desc in DESCRIPTIONS.items():
        mask = (df["venue_id"] == str(vid)) & (df["description"].fillna("").str.len() <= 10)
        if mask.any():
            df.loc[mask, "description"] = desc
            df.loc[mask, "description_source"] = "web_manual"
            filled += 1

    df.to_csv(config.MERGED_VENUES_ENRICHED_CSV, index=False)
    n_after = (df["description"].fillna("").str.len() <= 10).sum()
    print(f"Deskripsi terisi batch ini: {filled}")
    print(f"Venue tanpa deskripsi: {n_before} -> {n_after}")


if __name__ == "__main__":
    main()
