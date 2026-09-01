# Faz 8 — Bütçe ve ölçüm

## Fazın cümlesi

Faz 7 aracı canlı ölçtü ve 9.984 satırlık bir lint koşusundan **2.842 satır**
döndüğünü buldu — üçte biri. Bu bir yargı hatası değildi, **aritmetik** hataydı:
bir isteğe sığmayan yakalama parçalara bölünüyor, her parçaya "yüz yirmi satır
tut" deniyor, sonra cevaplar toplanıyordu. Dört parça, dört kere yüz yirmi.

Faz 8'in işi bu toplamayı bölmeye çevirmek — ve bunu ölçerek yapmak, çünkü
tavanın maliyeti "makul görünen sayıyı" seçmekle bilinemez.

## Bütçe bölünür, tekrar edilmez

`ceiling(budget, asks)` her isteğe `budget // asks` verir. Üç satırlık bir
fonksiyon, ama fazın var oluş sebebi:

```python
def ceiling(budget: int, asks: int) -> str:
    each = max(1, budget // asks)
```

`max(1, ...)` süs değil. Yeterince uzun bir yakalamada `budget // asks` sıfıra
düşer ve modele "sıfır satır tut" demiş olursunuz — bütçe sistemi kendi kendini
kapatır. Bunun bir mutasyonu var (`a share of the budget never falls to
nothing`) ve `max`'ı kaldırmak testi kırıyor.

Bir de kelime meselesi: `each == 1` iken metin "about 1 lines" diyordu. İsteme
giden her cümle modelin okuduğu bir cümledir; bozuk gramer bedava değil.

## Kodda kırpma yok

Bütçeyi aşan bir cevap gelirse akla ilk gelen çözüm listeyi kesmek. sift bunu
yapmıyor, ve gerekçe Faz 6'da `outline.py`'ye yazılmış olanın aynısı:

> Satırları sıralamak onları **okumayı** gerektirir.

Kısa olanları atın — tek başına duran bir `FAILED` gider. Uzun olanları atın —
yığın izi gider. Ortadan atın — yazı tura. Kod hangi satırın ne taşıdığını
bilmiyor; bilen taraf model. Bu yüzden `select` bütçeyi aşan cevabı **kesmez**,
modele geri verir.

## İkinci geçiş: ölçüm kendi tasarımımı yanlışladı

`narrow()` ilk hâlinde kısa listeyi alıp **aynı soruyu** tekrar soruyordu. Kod
doğruydu, testler yeşildi. Sonra canlı koştum:

```json
{"kept": 359, "total": 1341, "asks": 4}
```

Dört istek: bir ilk geçiş + üç daraltma turu, hepsi harcanmış, 120 bütçesine
yakınsamamış. Sebep koddaki bir hata değil, **sorunun kuruluşu**:

> "Hangi satırlar önemli?" diye sorulan bir kısa liste, zaten hepsi önemli
> satırlardan oluşuyor. Model "hepsi" diyor — ve haklı.

İkinci geçiş, birinci geçişin tekrarı olamaz. Listenin **zaten cevap olduğunu**
ve buna rağmen uzun kaldığını söylemesi gerekiyor. `NARROWING` bunu söyleyen üç
cümle, ve isteme eklendiği yer `question + NARROWING`.

Aynı komut, düzeltmeden sonra:

| | aynı soru ikinci kez | `NARROWING` ile |
|---|---|---|
| tutulan satır | 359 / 1.341 | **149 / 1.341** |
| gösterilen | 24.152 B | **11.129 B** |
| yakalamanın oranı | %31,5 | **%14,5** |
| istek sayısı | 4 | 4 |

Aynı maliyetle çıktı yarıdan fazla küçüldü. Fark tek bir istem paragrafı.

149 hâlâ 120'nin üstünde ve öyle kalıyor: üç tur bitince elde ne varsa o geri
veriliyor. 29 satır için dördüncü bir model çağrısı ödemek, kırpmamak uğruna
katlanılan bir fazlalıktan daha pahalı. `test_a_view_still_over_budget_after_
three_rounds_comes_back_long` tam bu durumu koruyor: uzun gelen cevap uzun
kalır, sessizce kesilmez.

## Beklemek, hesaplamak değil

Ölçüm bir şeyi daha gösterdi: araç yavaştı ve yavaşlığın tamamı **bekleme**ydi.
633 KB'lik bir lint koşusu 120.000 karakterlik yedi isteğe bölünüyor ve bu yedi
istek sırayla gönderiliyordu — süreç on dakika boyunca sokette bekliyor, CPU
sıfır.

Bu yedi parça **birbiriyle ilgisiz**: örtüşmüyorlar ve cevapları küme birleşimiyle
toplanıyor. Küme birleşiminin sırası yok, dolayısıyla aynı anda sormak *neyin
döndüğünü* değiştirmez, yalnızca *ne kadar beklendiğini* değiştirir. `_ask_all`
bunu yapıyor; `SIFT_WORKERS` ile ayarlanıyor, varsayılan 6.

Daraltma turları bilerek sıralı bırakıldı. Her tur bir öncekinin cevabı hakkında
soru soruyor; orada paralelleştirilecek bir şey yok.

Aynı komut, ölçülmüş hâliyle:

| | seri | paralel ilk geçiş |
|---|---|---|
| duvar saati | 15 dk'da **bitmedi** (durduruldu) | **751 sn (12,5 dk)** |
| istek | — | 12 (9 paralel + 3 bağımlı tur) |
| tutulan | — | 163 / 11.868 satır (%2,6) |

Kazanç ~2 kat, 7 kat değil — ve sebebi kayda değer: **duvar saatini artık ilk
geçiş değil, üç bağımlı daraltma turu belirliyor.** Paralellik bittiği yerde
bitiyor.

Aynı düzeltme `test/budget.py`'ye de uygulandı, ve orada bir bedeli çıktı:
altı eşzamanlı istek uç noktayı reddettirdi, `Bridge` de reddi merdivende bir alt
modele düşerek karşıladı. Sonuç, satırları farklı modellerin cevapladığı ve
dolayısıyla **hiçbir şeyi kıyaslamayan** bir tabloydu. İki şey eklendi: her satır
kendisine cevap veren modelleri kaydediyor, ve ölçüm merdiveni tek basamağa
sabitliyor. Sabitlenmiş merdivende reddedilen istek sessizce küçülmüyor, görünür
bir "cevap yok" oluyor.

## Kısa görünüm mü, eksik görünüm mü

`select` cevapsız dönen isteği atlıyordu. Bu, iki bambaşka şeyi birbirinden
ayırt edilemez kılıyor:

> Yedi istekten birinin cevaplandığı bir görünüm, yedisinin de cevaplandığı bir
> görünümle **aynı** okunuyor. İkisi de "çok satırdan az satır" diyor, aynı
> kelimelerle, aynı kendinden eminlikle. Farkları şu: biri bir seçim, diğeri bir
> boşluk.

`View.unanswered` bu sayıyı tutuyor, `view.py`'deki `silence()` alt bilgiye
`· 6 questions unanswered` diye ekliyor, `view.json`'a da yazılıyor.

Dürüst olmak gerekirse: bu sayacı, `wire.py`'nin 11.587 satırdan **19 satır**
döndürdüğü koşuyu açıklamak için ekledim. Temiz koşuda hipotez **doğrulanmadı** —
`unanswered: 0` ile 163 satır geldi. 19 satırlık sonuç, `budget.py`'nin API'yi
altı koldan yorduğu anın hemen ardına denk gelmişti. Sayaç yine de duruyor,
çünkü o gün görülemeyen şey bugün görünür; ama sebebi buydu diye yazamam.

## Korpus kıyası

22 örnek, 4 bütçe, merdiven tek basamağa sabit
(`nvidia/nemotron-3-ultra-550b-a55b`), aynı anda 6 istek:

| bütçe | gerekli satır | gürültü | gösterilen | istek | kaç örnek | sessiz |
|---|---|---|---|---|---|---|
| 20 | 116/118 | 94/334 | 228/510 (%45) | 21 | 19 | 3 |
| 60 | 121/123 | 134/351 | 284/523 (%54) | 19 | 19 | 3 |
| **120 (varsayılan)** | **138/140** | 167/417 | 336/621 (%54) | 22 | 22 | 0 |
| tavan yok | 137/140 | 109/417 | 279/621 (%45) | 22 | 22 | 0 |

Okunması gereken üç şey var.

**Varsayılan tavan, tavansızdan iyi.** 140 gerekli satırın 138'ini tutuyor;
tavansız 137. Yani bütçe bölmek bu korpusta bir şey kaybettirmiyor — Faz 8'in
bütün gerekçesi buydu ve ölçüm onu doğruluyor.

**Bedeli gürültüde.** 120 tavanı 417 gürültü satırının 167'sini (%40) geçiriyor,
tavansız 109'unu (%26). Yani varsayılan cömert: gerekli satırı kaçırmıyor ama
yanında fazlasını getiriyor. Sıkı tavanlar (20, 60) gürültüyü kırpıyor.

**20 ve 60 satırları doğrudan kıyaslanamaz.** Her birinde 3 örnek hiç
cevaplanmadı, dolayısıyla o satırlar 22 değil 19 örnek üzerinde. Tablo bunu
`kaç örnek` ve `sessiz` sütunlarıyla söylüyor; söylemeseydi %98 ile %98 aynı
görünür, biri 19 örnekten diğeri 22'den olurdu.

Varsayılanın kaçırdığı iki satır:

```
gradle-ko 32: BUILD FAILED in 41s
gotest-zh  8: === RUN   Test优惠券/折扣不得超过总价
```

Bunlardan **`gradle-ko 32` her ayarda kaybediliyor** — tavanla da, tavansız da.
Onu tavana yazmak, modelin bir yargısını aritmetik kusuru diye raporlamak olur.
`gotest-zh 8` ise tavansızken tutuluyor, 120'de tutulmuyor: tavanın gerçek
bedeli, ve tek satır.

## Ölçüm aracının kendi iki kusuru

Yukarıdaki tablo ilk denemede çıkmadı. İlk sabitlenmiş koşu şunu bastı:

```
   120   103/140   ...   17
The default budget (120) lost a required line. That is a bug.
```

Yani varsayılan bütçe 140 gerekli satırın 37'sini kaybediyordu ve araç bunu
kendi kusuru ilan ediyordu. İkisi de yanlıştı, iki ayrı sebepten.

**Bir: eşzamanlılık kendi karesini alıyordu.** `SIFT_WORKERS` iki yerde
okunuyor — `budget.py`'de "aynı anda kaç örnek", `distill.select()` içinde
"aynı anda kaç parça". Aralarında hiçbir bağ yoktu, dolayısıyla çarpıldılar:
6 × 6 = **36 eşzamanlı istek**. Ücretsiz uç nokta reddetti, merdiven sabit
olduğu için reddedilen istek "hiç cevap yok"a döndü, ve o örneklerin gerekli
satırları "bütçe kaybetti" hanesine yazıldı. `main()` artık iç geçişi 1'e
sabitliyor; dıştaki sayı toplam eşzamanlılık oluyor.

**İki: cevapsız örnek, bütçe kaybı gibi sayılıyordu.** Bu, ürün tarafındaki
`View.unanswered` dersinin ölçüm tarafındaki birebir karşılığı: *bakılmamış
örnekle kaybedilmiş satır aynı okunuyor.* `Row` artık `silent` listesi ve
`counted` sütunu tutuyor, cevapsız örnek satırın aritmetiğine hiç girmiyor.

Bir üçüncüsü de tablo temizlendikten sonra görüldü: hüküm, **her ayarda
kaybedilen** bir satırı tavana yazıyordu. `verdict()` artık varsayılanın
kaçırdıklarını tavansız satırın kaçırdıklarıyla karşılaştırıyor; ortak olanlar
"tavanın işi değil" diye ayrı basılıyor. Bu fonksiyon saf, dolayısıyla ağsız
sınanabiliyor — dört testi var.

Kural: **ölçüm aracı da koddur ve aynı özeni hak eder.** Bu yüzden mutasyon
bataryasının kapsamı `src/` ile sınırlı kalmadı; `test/budget.py`'nin dört
kuralı da bataryada:

| kural | mutasyon ne yapıyor |
|---|---|
| cevapsız örnek satıra girmez | `if view is None` |
| satır kullanabildiği örnekleri sayar | `counted += 0` |
| her ayarda kaybedilen satır tavana yazılmaz | `cost = list(missed)` |
| kıyas satırı yoksa her kayıp tavanındır | `return [], []` |

## Kazanç raporu

Her görünüm, hangi ön yüzden gelirse gelsin, `captures/<handle>/view.json`
dosyasına kendi faturasını yazar:

```json
{"handle": "8e00a4ab", "raw_bytes": 76756, "shown_bytes": 11129,
 "kept": 149, "total": 1341, "model": "...", "asks": 4}
```

Yazma yeri `view.py` — yani **iki ön yüzün paylaştığı merdiven**. cli.py'ye
yazsaydım MCP koşuları faturasız kalırdı; `test_a_run_over_the_wire_is_billed_
the_way_one_at_a_terminal_is` bunu tel üzerinden doğruluyor.

Üç ayrıntı bilerek böyle:

- **`contextlib.suppress(OSError)`** — muhasebe tutulamıyorsa kaybedilen rapordur,
  koşu değil. Kullanıcının komutu, defter yazılamadı diye başarısız olmaz.
- **Görüntülenmeyen yakalama tabloya girmez.** Sıfır bayt gösterilmiş gibi
  saymak kazancı şişirirdi; `savings()` `view.json`'ı olmayanı atlar.
- **Ham bayt, yakalamanın baytıdır** — görünümün değil. Fatura, "gösterilene
  karşı gösterilmeyecek olan"dır.

### `sift stats` neden araç değil

Sunucuda hâlâ üç araç var. `stats` bir **makbuz**: insanın "bu şey ne kadar
kazandırdı" sorusunun cevabı. Model bunu sormaz, sorsa da cevabı işine yaramaz.
`sift list` için Faz 7'de verilen gerekçenin aynısı.

```
handle        captured       shown    part  asks  command
8e00a4ab      76,756 B    11,129 B   14.5%     4  ruff check --select ALL --no-cache src/

1 run · 76,756 B captured · 11,129 B shown · 14.5% of it · the other 85.5% is on disk, not gone
```

Son cümle özellikle böyle. sift bir şeyi **saklamıyor**, göstermiyor; %85,5 hâlâ
diskte ve `sift peek` ile numarasından istenebilir. Rapor bunu her defasında
tekrar söylüyor, çünkü aracın tek satılık iddiası bu.

## Testler ve mutasyonlar

34 yeni test (373 → 407), 29 yeni mutasyon (55 → 84). Faz 8'in kuralları:

| kural | mutasyon ne yapıyor |
|---|---|
| bütçe bölünür, tekrar edilmez | `each = budget` |
| pay hiç sıfıra düşmez | `max(1, ...)` kaldırılır |
| bütçe modele ulaşır | `share = ""` |
| her istem tek cevap biçimiyle biter | `ANSWER_FORMAT` düşürülür |
| uzun cevap geri verilir | daraltma atlanır |
| **ikinci geçiş farklı soru sorar** | `NARROWING` düşürülür |
| kısa liste yakalamanın numaralarını korur | 1'den yeniden numaralanır |
| daraltma yalnız düşürür | `& chosen` kaldırılır |
| boş tur öncekini bozmaz | `not kept` kontrolü kaldırılır |
| daraltma kısaltmayı bırakınca durur | `>= len(chosen)` kaldırılır |
| tur sayısı sabittir | `while True` |
| taslak kendi bütçesini alır | `budget=None` |
| fatura görünüme kesilir | ham bayt görünümün baytı yapılır |
| yazılamayan defter yalnız raporu götürür | `suppress` kaldırılır |
| görüntülenmemiş yakalama tabloya girmez | sıfırla doldurulur |
| bir yakalamanın parçaları aynı anda sorulur | havuz atlanır, sıraya girilir |
| kaç tanesinin aynı anda sorulacağı çağıranındır | `max_workers=1` |
| bu sayı hiç birin altına düşmez | `max(1, ...)` kaldırılır |
| cevapsız dönen istek sayılır | `unanswered += 0` |
| sayı sayıldığı fonksiyondan çıkar | `unanswered=0` |
| okuyucuya bakılmayan kısım söylenir | `silence(view)` düşürülür |
| sessizlik yalnız varsa bildirilir | koşul hep doğru yapılır |
| fatura cevapsızları saklar | `unanswered=0` |

Paralel ilk geçiş test yardımcısını da etkiledi: `_Judge.ask` artık birkaç iş
parçacığından çağrılıyor, sorunun kaydı ile cevabın seçimi tek kilit altında
oluyor. Sıraya bağlı iki iddia gevşetildi — parçalar artık kesildikleri sırayla
gelmiyor, o yüzden başladıkları numaraya göre sıralanıp kıyaslanıyorlar. Kural
aynı kaldı, yalnız "sırayla soruluyor" varsayımı düştü; zaten düşürülen de oydu.

Beş capa bu fazda taşındı: `_windows()` gitti, yerine `_batches()` geldi.
**Kod taşımak mutasyon capalarını sessizce kırar** — Faz 7'nin dersi. Batarya
öncesi ön kontrol:

```python
bad = [x for x in m.MUTATIONS if x.path.read_text(encoding="utf-8").count(x.before) != 1]
```

Bataryanın ilk tam koşusu **79/80** verdi. Kaçan kural şuydu: *"yazılamayan
defter yalnız raporu götürür."* `store.record()` yazmayı `contextlib.suppress`
ile susturuyor; mutasyon bu susturmayı kaldırdığında testler yine yeşildi.

Sebep, testin yanlış yerden sorulmasıydı. Kuralı `cli.main` üzerinden sınıyordum,
ama komut satırının görünüm inşasının etrafında kendi ağı var:

```python
except Exception as exc:  # the view is optional; the output is not
```

O ağ, `store`'un sözünü tutup tutmadığından bağımsız olarak testi yeşil tutuyor.
Yani test, `store`'u değil `cli`'yi ölçüyordu. Test `view.best_view()` seviyesine
indirildi — ağın altına — ve mutasyon aynı gün yakalandı: **80/80**.

Genel hâli: **bir kuralı, o kuralın altında ikinci bir emniyet varken sınayamazsın.**
Yeşil olan, sınadığını sandığın şey değil, ondan önce devreye giren şeydir.

## Bu fazın dersi

Yeşil test, kodun doğru olduğunu gösterir; **sorunun doğru sorulduğunu
göstermez.** `narrow()` yazıldığı hâliyle testlerinden geçiyordu ve işe
yaramıyordu. Bunu bulan şey bir test değil, canlı bir koşu ve `view.json`'daki
`"asks": 4` idi.

Ölçüm bu yüzden fazın adında: bütçe kodun yarısı, ölçüm diğer yarısı.
