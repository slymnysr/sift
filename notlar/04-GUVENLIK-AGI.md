# Faz 4 — Güvenlik ağı ve komut satırı

`src/sift/fallback.py` ve `src/sift/cli.py`.

README'nin üçüncü kuralı bu fazda kanıtlanıyor: **hiçbir şey komutunuzu
bozamaz.** Anahtar yok, ağ yok, uç nokta meşgul, cevap saçma, damıtıcıda hata —
hepsinin sonu ekranda çıktı ve komutun kendi çıkış kodu.

## Yedek neden hiçbir şey "anlamıyor"

Buradaki cazibe zekâ göstermek: "error" kelimesini aramak, yığın izini tanımak,
satırları ne kadar endişe verici göründüklerine göre puanlamak.

O tasarım tam olarak bu projenin kurtulmak için baştan yazıldığı şey. Böyle
desenler kılık değiştirmiş bir dil listesidir — İngilizce için ve yazanın
bildiği beş on biçim için çalışır, Türkçe için, Japonca için, geçen hafta çıkmış
bir araç için sessizce başarısız olur. Üstelik **kendinden emin görünerek**
başarısız olur.

Bu yüzden yedek anlam hakkında hiçbir iddiada bulunmuyor. Başı ve sonu gösterir,
atladığını işaretler. Baş neyin çalıştırıldığını, son nasıl bittiğini söyler. Bu
bir derleyici için de, test koşucusu için de, kurulum aracı için de, kabuk
betiği için de doğrudur ve hiçbirini tanımaya ihtiyaç duymaz.

Modelden **kötüdür**. Öyle olması gerekiyor. Olmaması gereken şey **yanlış**
olması ve iddiada bulunmayan bir kural yanlış iddiada bulunamaz.

```
HEAD = 10               ilk satırlar: ne çalıştırıldı, ilk ne bozuldu
TAIL = 40               son satırlar: sonuç, özet, çıkış
TAIL_WHEN_FAILED = 80   başarısız koşum sebebini sonda ve daha uzun anlatır
```

`model` alanı boş bırakılıyor — okuyanın hangi görünüme baktığını ayırt etmesi
için. Hangi satırların, kim tarafından seçildiğini bilen biri gerisini okumaya
gidip gitmeyeceğine kendisi karar verir.

## Komut satırı: üç komut

```
sift run [--timeout SANİYE] [--shell] [--] KOMUT...
sift peek TUTAMAÇ [İLK] [SON]
sift list [ADET]
```

**`argparse` kullanılmıyor.** İnatçılık değil: `sift run -- pytest -x --lf`
`sift`'e kendi bayrakları olan bir komut veriyor ve yardımcı olacak kadar akıllı
her ayrıştırıcı onları yiyecek kadar akıllıdır. Komut kelimesinden sonrası
dokunulmadan geçiyor. Bayrak yalnız **başta** bayraktır; bunun bir mutasyonu var.

**Çıkış kodu komutun kendisinin.** `pytest` başarısız olunca başarısız olan bir
betik, `sift run -- pytest` olduğunda da başarısız olmak zorunda. Aksi hâli bu
aracı en çok işe yarayacağı yerde kullanılamaz yapardı. Zaman aşımı `124`
(kabukların ve `timeout(1)`'in dili), çalıştırılamayan komut `127` — ikisi de
ödünç alındı, icat edilmedi.

**Görünüm stdout'a, altbilgi stderr'e.** Bir görünümü bir yere borulamak,
`sift`'in yorumunu da borulamak anlamına gelmesin.

```
sift f5213d56 · exit 1 · 8/467 lines · nvidia/nemotron-3-ultra-550b-a55b · 0.0s
```

## Canlı doğrulama (2026-08-31)

400 satır indirme gürültüsü + 59 satır derleme + bir bağlama hatası ve yığın izi
(467 satır, çıkış 1):

| Yol | Sonuç |
|---|---|
| Model erişilebilir | **8/467 satır** — yalnız `derleniyor:` satırı, hata ve yığın izi; ultra 550B seçti |
| `SIFT_BASE_URL` ulaşılamaz | **90/467 satır** — baş 10 + kuyruk 80, altbilgi sebebi yazıyor, çıkış kodu 1 |

İkisinde de gösterilen her satır yakalamadan geldi ve çıkış kodu korundu.

## Zemin: seçen her şey çökerse

`_view` damıtıcıdaki her hatayı yakalayıp yedeğe düşüyor. Peki **yedek** de
çökerse? O zaman kullanıcı hem görünümü hem çıktısını hem de üzerine işlem
yapacağı çıkış kodunu kaybederdi — çünkü Python'un yığın izi kendi çıkış kodunu
getirir ve komutunkini örter.

`_last_resort` bu yüzden var: seçen her şey başarısız olduğunda **bütün
satırları** basıyor. Buraya düşmek `sift`'te hata olduğu anlamına gelir ve
çıktıyı kısaltan kısımdaki bir hata **kısaltmaya** mal olmalı; çıktıya ya da
çıkış koduna değil. Testi hem damıtıcıyı hem yedeği patlatıyor ve yine iki
satırın da ekranda, çıkış kodunun 3 olmasını bekliyor.

## Konsolun kod sayfası çıktıyı yutmasın

Yakalama herhangi bir dili taşıyabilir ve boşluk işareti `─` ile `·` çiziliyor.
Hâlâ eski bir kod sayfasına ayarlı bir konsol — Windows'ta varsayılan —
kodlayamadığı ilk karakterde hata fırlatır. O zaman koşum, komutla ilgisi
olmayan bir terminal ayrıntısı yüzünden kaybolur.

`_speak_utf8` stdout ve stderr'i UTF-8 + `errors="replace"` ile yeniden
yapılandırıyor. Bir glif kaybetmek, koşumu kaybetmekten iyidir. Küresel bir araç
için bu bir süs değil: çıktısı Japonca olan bir derleyici, Windows'ta
çalıştırıldığı için sessizce kullanılamaz hâle gelmemeli.

## Faz 1'de verilmiş bir kararın geri alınması

`store.read_raw` hiç var olmayan bir tutamaç için `b""` dönüyordu ve Faz 1'de
bunun testi vardı: *"bilinmeyen tutamaç çökmek yerine yok gibi okunur."*

Faz 4 bunun bedelini gösterdi: `sift peek yanlisyazim` hiçbir şey basıp
`lines 0-0 of 0` diyor. Ekranda **boş bir yakalama** ile **var olmayan bir
yakalama** birbirinin aynı görünüyor ve zıt şeyler söylüyorlar. Birincisiyle
cevaplamak, kullanıcıyı kendi komutunda olmayan bir hatayı aramaya yollar.

Artık `FileNotFoundError` fırlatıyor. Faz 1'in asıl kararı — *`raw` var ama
`meta.json` yoksa baytlar yine verilir* — değişmedi; o **yarıda kalmış koşum**
ve üçüncü bir durum. Test adı ve iddiası bu üç durumu ayıracak şekilde
yeniden yazıldı.

## README artık koddan üretiliyor

`test_the_readme_shows_the_marker_this_code_actually_writes` README'deki boşluk
işaretini `distill.gap()` ile üretip dosyada arıyor. Bir biçim dizgesi ve bir
README aynı şeyi söyleyen iki yerdir ve biri hiç çalıştırılmaz; bu test
çalıştırılmayanı sesli biçimde kırıyor.

Bu sırada README'deki örnek tutamaç düzeltildi: gerçek tutamaçlar 8 onaltılık
karakter, `a3f1` değil.

## Mutasyon bataryası

39 kural (Faz 1'den 6, Faz 2'den 9, Faz 3'ten 11, Faz 4'ten 13). Tam koşum
37/37, sonradan eklenen iki son-çare kuralı ayrıca 1/1 ve 1/1.

## Sırada

Faz 5 — dil bağımsızlığı: dünya dilleri ve yazılım dilleri korpusu, ve seçimin
gerçekten dilden bağımsız olduğunun ölçülmesi. Bu fazın iddiası ("liste yok")
ilk kez sayıyla sınanacak.
