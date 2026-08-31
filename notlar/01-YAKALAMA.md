# Faz 1 — Yakalama

Komutu `sift` kendi çalıştırır, yazdığı her baytı diske alır, `peek` ile
baytı baytına geri verir. Faz 1'in kapsamı budur; damıtma Faz 3'te.

## Ne var

| Dosya | Sorumluluk |
|---|---|
| `src/sift/store.py` | Yakalamanın diskteki yeri: `$SIFT_HOME/captures/<tutamaç>/{raw,meta.json}` |
| `src/sift/capture.py` | Komutu çalıştırma, çıktıyı boruya bağlama, süreyi tutma |
| `src/sift/peek.py` | Ham baytlardan istenen satır aralığını geri verme |
| `test/test_capture.py` | 17 test |
| `test/test_package.py` | 3 test (Faz 0) |

**Durum:** 20 test yeşil, `ruff check src test` temiz, mutasyon 6/6.

## Kararlar ve gerekçeleri

**stderr boruya stdout ile birleşiyor.** Ayrı tutulsa sonradan sıraya dizmek
tahmine kalır; boruda birleşince sırayı işletim sistemi kurar ve terminalde ne
görünecekse o saklanır. Yargılanmaya değer olan, insanın göreceği şeydir.

**Baytlar doğrudan diske.** Bir saat yazan komut, onu izleyen süreci
büyütmemeli. Tampon dosyanın kendisidir; kaçak bir `yes` diske mal olur — disk
ucuz ve geri alınabilir, bellek ikisi de değil.

**`meta.json` tamamlanma işareti.** `raw` var ama `meta.json` yoksa koşum yarıda
kalmıştır: `store.load` yok der, `store.read_raw` yazılabilmiş baytları yine de
verir. Baytlar her zaman saklanmaya değer; onlar hakkındaki iddialar uydurulmaya
değmez.

**Tutamaç saat + PID + komuttan türüyor.** Yalnız komuttan türetilse aynı komut
ikinci kez koşturulduğunda çakışırdı — ki bu istisna değil, olağan durum.

**`peek` aralığı reddetmez, kırpar.** "3.914 satır gösterilmedi" okuyan biri bir
sayı tahmin eder; tahmin hakkında hata vermek yerine en yakın gerçek satırları
vermek işe yarar.

**`shell=True` var ama varsayılan değil.** Boru ve joker insanların gerçekten
yazdığı şeyin yarısı; reddetmek kullanıcıyı izlenmeyen terminale geri iter.
Argüman listesi kabuk tarafından yeniden yorumlanamaz, önce ona uzanılır.

## Mutasyonun bulduğu gerçek hata

Testler yeşildi. Mutasyon bataryası (`sift_disli1.py`) "yalnızca ebeveyni öldür,
çocuklar yetim kalsın" mutasyonunu **yakalayamadı**. İki ayrı kusur çıktı:

**1. Testin kendisi dişsizdi.** `pgrep -f "time.sleep(60)"` — `pgrep` genişletilmiş
düzenli ifade okur, parantezler grup olur, desen aslında `time?sleep60` arar.
Hiçbir komut satırında böyle bir dizi yok: çocuklar öldürülse de öldürülmese de
boş döner, test her hâlükârda geçer. Artık her koşum kendi rastgele onaltılık
belirtecini üretiyor — düzenli ifade anlamı taşımıyor ve başka bir koşumun
sürecine denk gelemiyor.

**2. Asıl hata `capture.py`'deydi.** Mutasyon altında `run()` 2 saniye yerine
**60 saniye** sürüyordu. Sebep: boru, yazma ucunu tutan *herhangi* bir süreç
yaşadığı sürece açık kalır. Bloklayan `read()` ve ardından `proc.stdout.close()`
(tamponun kilidini bekler) yetim süreç çıkana kadar dönmüyordu. Test `pgrep`'e
vardığında yetim kendi 60 saniyesini doldurup çıkmış oluyordu — görülecek bir
şey kalmıyordu.

Bu yalnız mutasyonun sorunu değildi: `setsid` ile süreç grubundan çıkan bir
süreç (arka plan servisi bırakan bir derleme, kendi oturumuna geçen bir test
koşucusu) sağlam kodda da `run()`'ı süresiz asardı. **Zaman aşımı sözü
tutulmuyordu.**

Düzeltme: boru artık `selectors` ile izleniyor, okuma yalnız veri olduğu
söylendiğinde yapılıyor, durdurma bayrağı gelince ve okunacak bir şey kalmayınca
iş bitiyor. Boruyu ve dosyayı kapatma sorumluluğu tamamen pompa iş parçacığında —
`run()` içinden kapatmak, okuyan bir iş parçacığının altından kapatmak demektir
ve sınırlı bir bekleme tam da böyle sınırsız hâle gelir. Windows'ta `selectors`
yalnız yuvalardan anlar; orada boru kapanana kadar beklenir ve bu, `_new_session`
içinde yazılı olan sınırın aynısıdır.

Bunu çivileyen test: `test_a_process_that_escapes_the_group_cannot_hold_the_run_open`.
Yalnız süreyi değil, **veriyi** de ölçüyor — boru bırakıldığında ondan geçmiş
baytların bırakılmadığını, zaman aşımından önce yazılanların diskte okunabilir
olduğunu doğruluyor.

## Ders

Bir testin geçmesi, o testin bir şey kanıtladığı anlamına gelmez. Bu turda
kanıtlanmayan iki şey vardı ve ikisi de yeşil görünüyordu: desen hiçbir zaman
eşleşmiyordu, ölçülen olay ölçüm anına kadar kendiliğinden bitiyordu. Mutasyon
olmasa ikisi de fark edilmezdi.

Kural olarak kalsın: **bir testin gözlediği durumun testin baktığı anda hâlâ
duruyor olduğunu ayrıca doğrula.** Yokluğa bakan bir iddia, varlığın hiç
oluşmadığı ihtimalini de elemek zorundadır — bu yüzden kaçak testi önce
belirteç dosyasının yazıldığını görüyor, sonra sürecin ölmüş olmasını arıyor.

## Sırada

Faz 2 — model köprüsü: NVIDIA NIM istemcisi, basamaklı model
(ultra → super → lightning), zaman aşımı, yeniden deneme, anahtar yokken
sessizce çalışmaya devam.
