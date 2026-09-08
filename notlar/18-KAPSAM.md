# Faz 18 — Kapsam: hook

## Fazın cümlesi

MCP sunucusu yalnız kendisine sorulanı damıtabilir. Bir kodlama ajanının kendi
başına çalıştırdığı kabuk komutları — ki çoktur — konuşmaya olduğu gibi düşer.
Bu faz o boşluğu **vekil kullanmadan** kapatıyor: istemci kabuk komutunu önce
buraya gönderiyor, sift çalıştırıyor, geri dönen bir görünüm oluyor.

## Vekil neden yok

winnow'da `proxy.py` var: tüm konuşmayı API'ye giderken damıtan bir HTTP vekili.
Kapsamı daha geniş ve sift'e eklenmedi.

Sebep mimari: bir vekil, komutun çıktığı yerde durmak değildir. Ayrı bir güven
modeli ister (trafiğin tamamı oradan geçer), ayrı bir çalışma ömrü ister (sürekli
açık bir sunucu) ve sift'in "yalnız kendi çalıştırdığını görür" duruşunu bozar.
Bu, sift'e eklenecek bir özellik değil, ayrı bir üründür.

Hook aynı boşluğu duruşu bozmadan kapatıyor: komutu yine sift çalıştırıyor,
araya giren bir şey yok.

## Her şey yönlendiriliyor

En cazip ve en yanlış tasarım şuydu: "gürültülü görünen" komutları yakala.

O liste, kılık değiştirmiş bir araç listesidir. `pytest`'i ve `cargo`'yu bilir,
şirket içi betikte yanılır, kırk bin satır basan komut hakkında kendinden emin
biçimde susar. Ve **ilkesel olarak doğru olamaz**: bir komutun ne kadar
basacağı, çalışmadan önce bilinemez.

Her şeyi yönlendirmek bedava, çünkü kısa çıktının görünümü kendisidir: bütçe
ancak bütçeden fazlası varken devreye girer. On iki satır girer, on iki satır
çıkar.

## Açığa düşerek başarısız oluyor

Okunamayan olay, beklenmedik bir şekil, alttaki bir hata — hepsi boş cevapla
bitiyor ve istemci komutu kendisi çalıştırıyor, tıpkı olacağı gibi. **Kabuğu
bozan bir kapı, kapı olmamasından kötüdür.** Üçüncü kural, kırılması en pahalı
olduğu yerde.

`SIFT_HOOK=0` kapatıyor.

## Bu fazın dersi

**Bir kapsam genişletmesi, aracın duruşunu bozmadan yapılabiliyorsa öyle
yapılmalıdır.**

Vekil daha çok şey görürdü. Hook, sift'in gördüğü şeyin tanımını değiştirmeden
görülenin miktarını artırıyor — ve bu yüzden geri kalan her kural olduğu gibi
geçerli kalıyor.
