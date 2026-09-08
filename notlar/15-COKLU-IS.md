# Faz 15 — Çoklu iş

## Fazın cümlesi

Dört log dosyası, üç koşan komut, bir dizin. Tek tek sorulunca dört bekleme,
birlikte sorulunca bir bekleme. Ve bunu yaparken **aynı anda uçan istek sayısı
makineye söylenen sayıyı aşmamalı**.

## Asıl mesele paralellik değil, çarpılmama

Faz 8'de eşzamanlılık kendi karesini almıştı: `SIFT_WORKERS` iki katmanda
okunuyordu — kaç örnek aynı anda, ve bir örneğin kaç parçası aynı anda —
aralarında hiçbir bağ yoktu, çarpıldılar. 6 × 6 = 36 istek, ücretsiz uç nokta
reddetti, reddedilen istekler "bütçe kaybetti" hanesine yazıldı. Bir gün gitti.

Bu faz o hatayı tekrarlamayı kolaylaştırıyor: birkaç dosya, birkaç koşu, her biri
kendi içinde bölünmüş. Bu yüzden tavan **her çağıranın yeniden yapacağı bir
aritmetik olmaktan çıkıp bir kapıya dönüştü**:

```python
with in_flight():
    return judge.ask(...)
```

`distill.py` içindeki her istek buradan geçiyor. `many.py` istediği kadar iş
başlatabilir; havadaki istek sayısı yine makineye verilen sayıdır.

**Tek yerde uygulanan bir sayı çarpılamaz, çünkü çarpacak aritmetik kalmaz.**

Bu, sorumluluk dağılımının da kendisi: aritmetiği her çağırana bırakan bir tavan,
altı ay sonra o notu hiç okumamış biri tarafından yanlış hesaplanacak tavandır.

## Ölçülen

Test doğrudan bunu ölçüyor: 6 hedef, tavan 2, sahte modelin kaydettiği **anlık en
yüksek eşzamanlı istek = 2**. Ve 1'den büyük — yani paralellik gerçekten
çalışıyor, ölçülen şey "hiç paralel değildi" değil.

## Sıranın ağ tarafından belirlenmemesi

`many.together` cevapları **sorulduğu sırada** döndürüyor. Hangisinin önce
bittiği ağ hakkında bir olgudur; sıralamasını ona bırakan bir sonuç, aynı soruya
her seferinde farklı cevap verir.

## Beklemek, tekrar sormaktan ucuzdur

`follow --wait N` bir şey söylenene kadar tutuyor. Sebebi maliyet: **boş bir cevap
da bir araç sonucudur ve konuşmanın sonuna kadar orada durur.** Beş kez "henüz
bir şey olmadı" demek, bir kez bekleyip bir şey söylemekten pahalıdır.

`follow --all` de aynı fikrin diğer yüzü: üç build üç araç çağrısı ve üç sonuç
etmemeli. Bekleme bir kez, ilk konuşan üzerinden yapılıyor — sırayla beklemek
zaman aşımlarını toplardı.

## Bu fazın dersi

**Bir sınır, uygulandığı yerde bir tanedir; hesaplandığı yerde her çağıranda bir
tanedir.**
