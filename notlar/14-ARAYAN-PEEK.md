# Faz 14 — Arayan `peek`

## Fazın cümlesi

Bir görünüm sana *"3.914 satır gösterilmedi"* diyor ve aradığın kelimeyi
biliyorsun ama satır numarasını bilmiyorsun. `peek` artık desenle de arıyor.

## Ne değişti

`--grep` verildiğinde satır aralığı **cevap** olmaktan çıkıp **pencere** oluyor:
o aralıkta desene uyan her satır, okunabilsin diye çevresinde `--around` satırla
birlikte dönüyor.

Burada da yargı yok: desen çağıranın, eşleşme birebir, satırlar dosyanın kendisi.
Aradaki boşluklar görünümdeki aynı işaretle gösteriliyor — `render` yeniden
kullanıldı, çünkü ikinci bir boşluk işareti iki farklı doğru demektir.

## İki sayı, ve neden ikisi de lazım

Alt bilgi hem kaç satır gösterildiğini hem **kaç satırın eşleştiğini** yazıyor.

Bunlar farklı sayılar: her eşleşmenin etrafına bağlam ekleniyor ve cevap
sınırlanıyor. "40 satır" dört eşleşme de olabilir kırk eşleşme de. Yalnız
birincisi söylenen okuyucu, gördüğünün hepsi olup olmadığını bilemez.

## Sınır, eşleşme başına uygulanıyor

Tavan bitmiş kümeye değil, eşleşme eşleşme uygulanıyor: geri dönen şey
**ilk eşleşmeler bağlamlarıyla tam**, hepsi bağlamı kırpılmış değil. Kırpılmış
bir bağlam eksik eşleşmeden kötüdür, çünkü okuyucu kırpıldığını anlayamaz.

## Bu fazın dersi

**Bir aracın verdiği iki sayı farklı şeyler söylüyorsa, ikisi de yazılmalıdır.**

Tek sayı vermek kısa görünür; okuyucuyu yanlış bir güvene sokar. Faz 8'de aynı
ders `View.unanswered` ile öğrenilmişti: kısa görünüm ile eksik görünüm aynı
okunuyordu. Burada da kısa arama ile eksik arama aynı okunuyordu.
