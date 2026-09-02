# Sinyal Keşfi Literatür İncelemesi (CAN Tersine Mühendislik)

Tarih: 2026-08-30. Tüm metadata bu oturumda DBLP / GitHub API / USENIX üzerinden doğrulandı
(aksi belirtilenler hariç). Ana proje: Universal-CAN-BUS-Tool, MASTER_PLAN BÖLÜM 7.

## 1. Temel Yöntem Makaleleri

### 1.1 READ — Marchetti & Stabili (IEEE TIFS 2019) ⭐ DOĞRULANDI + ÖNEMLİ DÜZELTME
- **Tam ad:** "READ: Reverse Engineering of Automotive Data Frames"
- Yazarlar: Mirco Marchetti, Dario Stabili
- Yayın: IEEE Transactions on Information Forensics and Security, cilt 14, sayı 4, s. 1083–1097, 2019
- DOI: 10.1109/TIFS.2018.2870826 — https://doi.org/10.1109/TIFS.2018.2870826
- ⚠️ **DÜZELTME:** Önceki notlardaki "USENIX Security 2022, Shen et al." atfı **yanlıştır**.
  USENIX sayfası (/presentation/shen) Yun Shen'in Android-malware makalesine aittir.
  READ, TIFS 2019 makalesidir (DBLP kaydı: journals/tifs/MarchettiS19).
- **Yöntem:** Ham CAN kareleri üzerinde faz analizi: her bitin değişim (flip) zamanlaması
  istatistikleri çıkarılır; benzer değişim davranışına sahip bitler gruplanarak kare içindeki
  alan sınırları (field segmentation) ML olmadan bulunur. Kısa kayıtlarda (dakikalar) çalışır.

### 1.2 LibreCAN — Pesé et al. (ACM CCS 2019) ⭐ DOĞRULANDI + BAŞLIK DÜZELTMESİ
- Yayın başlığı (Crossref 2. tur teyidi): **"LibreCAN: Automated CAN Message Translator"**,
  ACM CCS 2019, s. 2283–2300, DOI: 10.1145/3319535.3363190. İlk yazar: Mert D. Pesé
  (GitHub: mdp93, mpese@umich.edu). (Önceki notlardaki "Protocol-Level Message
  Identification" başlığı arXiv ön-baskısına aittir.)
- **İki fazlı:** Faz 1 = bit-düzeyi analiz + SOM (Self-Organizing Map) kümelemesi ile alan keşfi;
  Faz 2 = OBD-II çevirisi (aynı araçtan OBD PID verileriyle eşleştirerek sinyal etiketleme).
- **Kod durumu:** github.com/mdp93/LibreCAN_CCS → **yalnızca README**; kaynak kodu yayınlanmamış.
  → Metodoloji referansı olarak kullanılacak, kod referansı DEĞİL.

### 1.3 CANMatch — Buscemi et al. (IEEE TVT 2021) ⭐ DOĞRULANDI
- "CANMatch: A Fully Automated Tool for CAN Bus Reverse Engineering Based on Frame Matching"
- Yazarlar: Alessio Buscemi, Ion Turcanu, German Castignani, Romain Crunelle, Thomas Engel
- IEEE Trans. Vehicular Technology 70(12):12358–12373, 2021. DOI: 10.1109/TVT.2021.3124550
- İlgili poster: "A Methodology for Semi-Automated CAN Bus Reverse Engineering", IEEE VNC 2021,
  s. 125–126, DOI: 10.1109/VNC52810.2021.9644673
- **Yöntem:** Frame matching — aynı ID'nin ardışık kareleri ve farklı senaryo kayıtları
  karşılaştırılarak değişen bitler hizalanır; farklı ECÜ'lerin aynı fiziksel büyüklüğü
  raporladığı durumlar çapraz korelasyonla bulunur.

### 1.4 Markovitz & Wool (Vehicular Communications 2017) ⭐ DOĞRULANDI (2. tur)
- **Tam ad:** "Field classification, modeling and anomaly detection in unknown CAN bus networks"
  (dergi sürümü — önceki "SAE World Congress" notu yanlış yönlendirmeydi; SAE sürümü
  ayrı bir yayın olabilir ancak doğrulanan kayıt dergidir).
- Yazarlar: Moti Markovitz, Avishai Wool.
- Vehicular Communications, cilt 9, s. 43–52, 2017. DOI: 10.1016/j.vehcom.2017.02.005
  — DBLP: journals/vcomm/MarkovitzW17. **Ek teyit:** READ (TIFS'19) kaynakçasında bu DOI
  birebir yer alıyor (Crossref ref8) → iki makale birbirini doğruluyor.
- Alan sınıflandırma şeması: SABİT / trend / rastgele / sayaç benzeri / CRC benzeri.
  Bit değişim istatistiklerine dayanır — keşif motorunun sınıflandırma katmanının temeli.

### 1.5 CAN-D — Verma et al. (IEEE TVT 2021) ⭐ DOĞRULANDI (2. tur — eski boşluk kapandı)
- **Tam ad:** "CAN-D: A Modular Four-Step Pipeline for Comprehensively Decoding Controller
  Area Network Data" (arXiv ön-baskısında başlık "Four-Step", önceki notlardaki
  "Modular and Scalable Pipeline" ifadesi yanlıştı).
- Yazarlar: Miki E. Verma, Robert A. Bridges, Jordan J. Sosnowski, Samuel C. Hollifield,
  Michael D. Iannacone (Oak Ridge National Laboratory).
- IEEE Trans. Vehicular Technology 70(10):9685–9700, 2021. DOI: 10.1109/TVT.2021.3092354
  (DBLP: journals/tvt/VermaBSHI21). arXiv ön-baskı: 2006.05993 (2020, açık erişim).
- **Yöntem (arXiv özetinden):** 4 adım — (1) sınır (start bit, length), (2) **endianness**,
  (3) **signedness**, (4) tanı standartlarıyla fiziksel yorumlama. Endianness dahil edince
  arama uzayı 128'den 4.72E21 tokenizasyona büyür; iki yeni sınır sınıflandırıcısı + ilk
  signedness sınıflandırıcısı (%97+ F-skor). 10 araçta ℓ1 hata önceki yöntemlerden 5× iyi.
  Hafif donanımda gerçek-zamanlı OBD-II sokak çözümü.
- **Tasarıma etkisi:** segmenter (PR-3) LE/BE ayrımını VEYA signedness sınıflandırmasını
  içermeli — önceki taslakta endianness vardı, signedness eksikti → tasarım §4 güncellendi.

### 1.6 ByCAN — Lin et al. (IEEE IoT-J 2024) ⭐ DOĞRULANDI (2. tur)
- **Tam ad:** "ByCAN: Reverse Engineering Controller Area Network (CAN) Messages From Bit
  to Byte Level."
- Yazarlar: Xiaojie Lin, Baihe Ma, Xu Wang, Guangsheng Yu, Ying He, Ren Ping Liu, Wei Ni.
- IEEE Internet of Things Journal 11(21):35477–35491, 2024. DOI: 10.1109/JIOT.2024.3435833
  (DBLP: journals/iotj/LinMWYHLN24). arXiv ön-baskı: 2408.09265 (açık erişim).

### 1.7 LibreCAN — Pesé et al. (ACM CCS 2019) ⭐ BAŞLIK DÜZELTMESİ (Crossref, 2. tur)
- **Yayınlanmış başlık (Crossref kaydı):** "LibreCAN: **Automated CAN Message Translator**"
  (alt başlık alanı) — önceki notlardaki "Protocol-Level Message Identification" yalnızca
  arXiv ön-baskısının adıymış. Atıfta dergi/konferans başlığı kullanılır.
- ACM CCS 2019, s. 2283–2300, DOI: 10.1145/3319535.3363190 (DBLP: conf/ccs/PeseSCNCS19;
  yazarlar: Pesé, Stacer, Campos, Newberry, Chen, Shin — Crossref 68 atıf).

### 1.8 READ — Crossref tam metadata (2. tur teyidi)
- IEEE TIFS cilt 14, sayı 4, Nisan 2019, s. 1083–1097, ISSN 1556-6013; Crossref 141 atıf;
  28 kaynağın arasında Markovitz&Wool 2017 (DOI yukarıda) ve "Comma Cabana" (cabana'nın
  kendisi!) dikkat çeker — kanıt zinciri yaklaşımımızın akademik öncülleriyle uyumlu.

### 1.9 Diğer doğrulanmış makaleler
- Huybrechts, Vanommeslaeghe, Blontrock, Van Barel, Hellinckx: "Automatic Reverse Engineering
  of CAN Bus Data Using Machine Learning Techniques", 3PGCIC 2017, s. 751–761,
  DOI 10.1007/978-3-319-69835-9_71 (ML yaklaşımı).
- Wen, Zhao, Chen, Lin: "Automated Cross-Platform Reverse Engineering of CAN Bus Commands
  From Mobile Apps", NDSS 2020 (açık erişim) — mobil uygulamadan komut çıkarımı.
- Varghese, Jiang, Rakib, Doss, Anwar: "Reverse Engineering-Guided Fuzzing for CAN Bus
  Vulnerability Detection", WISA 2024, s. 219–230, DOI 10.1007/978-981-96-1624-4_17.

### 1.10 DOĞRULANAMAYAN atıflar (kullanma!)
- "Uncovering the Mystery of CAN Message with Pixel-Wise Analysis" → DBLP + arXiv API'de
  YOK (2. turda arXiv tam_metin araması da yapıldı; 1108 sonuç tümü görüntü işleme).
  Bu başlık, orijinal kaynak teyit edilmeden teslimatlarda kullanılmayacak.

## 2. Sayaç / CRC Keşfi (en kritik boşluk — 1. turda KAPILDI, 2. turda DERİNLEŞTİ)
- **CANBUSconfidenceid** (numbpill3d, MIT, Python): rolling-counter + checksum/CRC-8 hipotez
  motoru — algoritma kataloğu ve çıktı modeli için bkz. arac_manzarasi.md §4.
- **opendbc safety/modes/*.h** (commaai, MIT): gerçek OEM implementasyonları — 2. turda
  **25 dosya lokal indirilip satır-satır damıtıldı**: tam marka kataloğu, jenerik
  doğrulama çerçevesi (MAX_WRONG_COUNTERS=5 debt modeli), pozisyon/algoritma dersleri →
  **opendbc_marka_guvenlik_profilleri.md** (PR-2 parametre setinin temel kaynağı).
- **CRC parametre kataloğu** (Greg Cook, reveng.sourceforge.io): 2. turda tüm CRC-8
  parametre setleri alındı + opendbc eşlemesi → **crc_referansi.md**.
  ⚠️ **Düzeltme:** 0x07 = CRC-8/**SMBUS**; SAE-J1850 = poly 0x1D/init 0xFF/xorout 0xFF
  (Chrysler gerçeklemesiyle birebir); VW = 0x2F = CRC-8/**AUTOSAR (8H2F)**.
- Sayaç tespiti: monotonic +1 (delta=1 oranı ≥ eşik), wrap tutarlılığı (mod 2^k), bit-field
  sayaçlar (Hyundai 0x386 deseni: ardışık olmayan bitler!), düşük rastgelelik skoru.
- Checksum tespiti: XOR, 8-bit toplamsal (ID/len dahil-hariç varyantları), nibble-toplam,
  popcount, ters-toplam (0xFF−sum), ones-complement; CRC-8 katalog taraması
  (crc_referansi.md §5); match_ratio = hipotezin kareler üzerindeki doğruluk oranı.

## 3. DBC Çıktı Formatı (özet)
- `BO_ <id> <name>: <len> <sender>` ; `SG_ <name> : <start>|<len>@<endianness><sign>
  (<scale>,<offset>) [<min>|<max>] "<unit>" <receivers>` ; `CM_` (yorum), `BA_` (attribute,
  GenMsgCycleTime = ms periyot), `VAL_` (value table/choices).
- `@1` = little-endian, `@0` = big-endian; `+`/`-` işaret.
- Programatik üretim: cantools (bkz. arac_manzarasi.md §1 — bu oturumda uçtan uca test edildi).
