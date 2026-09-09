# G6 — Diskin tavanı

**Tarih:** 9 Eylül 2026 · **Durum:** bitti

## Bulgu

`capture.py` ve `store.py` içinde tek bir boyut sınırı yoktu. `sift run -- yes`
zaman aşımına kadar diske yazardı — zaman aşımı verilmediyse komut bitene kadar,
yani hiç.

## İkinci kural bunu yasaklamıyor

*"Hiçbir şey silinmez"* kuralının yasakladığı şey **sessizce** atmaktır. Burada
hiçbir şey atılmıyor: yazılan yazılı kalıyor, her satırı `peek`'te duruyor.
Reddedilen şey öteki başarısızlık — başkasının da ihtiyaç duyduğu bir makinede
diski dolduran bir döngü.

Tavan **1 GiB**. Gerçek bir derleme kaydının çok ötesinde, `yes` için birkaç
saniye. `SIFT_MAX_CAPTURE=0` tavanı tamamen kaldırıyor: disk onların.

## Üçüncü kural bunu şekillendiriyor

Tavana varınca **saklama durur, okuma durmaz.**

Kimsenin boşaltmadığı bir boru dolar, ve borusu dolmuş bir komut **durur**. Yani
okumayı kesmek, bu aracın komutun davranışını değiştirmesi olurdu — üçüncü
kuralın yasakladığı tek şey. Bayt okunmaya devam ediyor; sadece saklanmıyor.

Sonuç: komut bitiyor, çıkış kodu kendisinin, ve altbilgi şunu söylüyor:

```
sift 9f2c41ab · exit 0 · 3/48,201 lines · … · kept the first 1,073,741,824 bytes of it
```

`peek` de aynı cümleyi taşıyor — bir kaydı iki hafta sonra açan kişi, elindekinin
koşunun tamamı olmadığını görmeli.

## Bataryanın yakaladığı iki şey

**Bir: eksik test.** "Tavanda saklama durur" mutasyonu **kaçtı**. Sebebi
testlerimin hepsinin tek yazışta tavanı aşmasıydı — oysa bir kaçak komutun
gerçekte yaptığı şey, tavana vardıktan **sonra da yazmaya devam etmek**. Şimdi
bir test sekiz ayrı yazışta 1.600 bayt gönderiyor ve saklananın tam olarak 50
bayt olduğunu iddia ediyor.

**İki: gereksiz kod.** Aynı mutasyon, düzeltmeden sonra da kaçtı. Sebebi bu kez
başkaydı: `if room <= 0` dalı bir **kural değil**, bir kısayoldu — kaldırıldığında
`chunk[:0]` aynı işi yapıyordu. Yani orada korunacak bir şey yoktu, ve doğru
cevap testi güçlendirmek değil **dalı silmekti.** Silindi; şimdi mutasyon gerçek
kuralı (`len(chunk) > room`) hedefliyor ve yakalanıyor.

Kaçan bir mutasyon her zaman "test eksik" demiyor. Bazen "bu satır bir şey
söylemiyor" diyor.

**Üç: varsayılanın kendisi.** "Tavanı 0 yap" mutasyonu da kaçmıştı — hiçbir test
*kimse ayar yapmadığında* ne olduğuna bakmıyordu. Oysa bu fazın teslim ettiği
şey tam olarak o. Artık iki test var: varsayılan gerçek bir tavan, ve saçma
yazılmış bir değişken tavanı sessizce kapatmıyor.
