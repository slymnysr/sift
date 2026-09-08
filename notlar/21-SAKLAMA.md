# 21 — Saklama: silen tek şey

**Nereden çıktı:** Headroom karşılaştırması. Onların önbelleğinin bir TTL'i var;
buranın hiçbir temizleme mekanizması yoktu — `store.py`'da `prune` yok, `expire`
yok, gün sayısı yok. `$SIFT_HOME` sonsuza büyüyordu.

## Kural nasıl korunuyor

İkinci kural "hiçbir şey silinmez" diyor ve bu faz silen bir komut ekliyor.
Çelişki değil, tek istisna ve tanımı dar:

**Kendiliğinden hiçbir şey süpürülmez.** Arka planda yaş kontrolü, tavan, "yol
üstünde toparlama" yok. `sift gc [DAYS]` silen tek şey ve **yazıldığı anda**
siliyor, öncesinde değil. Bu bir kullanıcı eylemi; araç kendi inisiyatifiyle
kullanıcının verisini silmiyor.

Bunun testi de var, ve o testin varlığı bu fazın asıl teslimi:

```python
def test_running_a_command_sweeps_nothing():
    # run, list, stats — üçü de çalıştıktan sonra 4000 günlük yakalama duruyor
```

Süpürülmeyen üç şey, üçü de kural:

| Ne | Neden |
|---|---|
| `running` işaretli koşu | Nasıl bittiğini kimse bilmiyor, gözetmeni hâlâ o dosyaya yazıyor |
| Yaşı belirlenemeyen yakalama | Tahminle silmek olurdu |
| Yeterince eski olmayan | Sorulan buydu |

## Mezar taşı: neden var, neden tek dosya

Yakalama dizini tamamen gidiyor, ve gittiği `$SIFT_HOME/gone.json` içine tek
satır olarak yazılıyor: **tutamak, tarih, boyut.** Komut değil.

Neden hiç iz bırakılıyor: iki hafta önce basılmış bir boşluk işareti hâlâ
`sift peek 9f2c41ab` diyor. İz olmadan bu, uydurulmuş bir tutamakla aynı cevabı
alır — *"böyle bir yakalama yok"*. Bu ikisi aynı şey değil ve okuyan kişi
ikisine farklı davranır.

Neden komut yazılmıyor: az önce silinen şeyin en tanımlayıcı parçası odur. Onu
saklamak silmeyi yarısından geri almak olur. Tutamak bir özet (hash), geri bir
şey vermiyor.

Neden dizin başına değil tek dosya: ilk hâli yakalama başına bir `gone.json`
bırakıyordu. 52 baytı tutmak için 4 KB'lık blok, ve depo yaşadığı sürece. Yer
açmak için yapılan süpürme, yer açmış olmanın kalıcı vergisini bırakıyordu.
Ayrıca dizin hiç gitmediği için README'nin "elle silinen bir yakalama dizini
hakkında tutulan her şeyi siler" cümlesi de doğru olmaktan çıkıyordu.

## Bu fazın ortaya çıkardığı kaza

Kodu yazdıktan sonra "duman testi" diye `store.sweep(1.0)` çalıştırıldı — sahte
bir depoda değil, **gerçek depoda**. 518 yakalama silindi.

Kaybedilen: hiçbir kullanıcı verisi. Üç farklı komut vardı, üçü de test
fikstürü (259 + 257 + 2), her biri 17-18 bayt.

Ama ortaya çıkardığı şey gerçek bir kusurdu: **testler kullanıcının gerçek
deposuna yazıyormuş.** `test_lines.py` `SIFT_HOME`'u izole etmiyordu — dosya
"bir satır nerede biter" hakkında ve hiçbir şeye dokunuyormuş gibi durmuyor, ama
bunu öğrenmek için gerçek komutlar çalıştırıyor ve hepsi `~/.cache/sift`'e
düştü. Kimse fark etmedi çünkü 17 bayttılar ve onları hiçbir şey listelemiyor.

Düzeltme dosyayı düzeltmek değil, **unutmayı imkânsız kılmak** oldu: izolasyon
`conftest.py`'ye taşındı, artık hiçbir test devre dışı bırakamıyor.

İkinci ders kendime: yıkıcı bir fonksiyonun duman testi, yıkacak bir şeyin
olmadığı yerde yapılır. Bu, 19. fazda yazılan dersin aynısının başka kılıkta
tekrarı — ve tekrar etmesi, dersin dosyaya yazılmasının yetmediğini gösteriyor.

## Ölçü

- Önce: hiçbir temizleme yolu yok, depo süresiz büyüyor.
- Sonra: `sift gc 30` yazılınca 30 günden eski yakalamalar gidiyor, ne gittiğini
  ve kaç bayt açtığını söylüyor, ve `peek` gidenlerin gittiğini biliyor.
- Bu fazın dört kuralının dördü de mutasyon bataryasında.
