# 22 — Yanıt önbelleği: aynı soruyu ikinci kez sormamak

**Nereden çıktı:** Headroom karşılaştırması. Onların en büyük kazancı sıkıştırma
değil, sağlayıcı önbelleğini bozmaması. Buradaki karşılığı daha basit ve daha
doğrudan: aynı metne ikinci kez sorma.

## İki maliyet, ikincisi geç görülen

Bir ajan düşen testi yeniden çalıştırır. Biri aynı CI logunu pazartesi ve salı
damıtır. Bir araç sonucu konuşmadan düşer ve yeniden çekilir. Üçünde de metin
bayt bayt aynı, soru aynı soru, ve cevap ikinci kez satın alınır.

**Görünen maliyet** bir istek: zaten cevaplanmış bir soru.

**Sessiz maliyet** cevabın farklı olabilmesi. Aynı soruyu iki kez alan bir model
biraz farklı bir satır kümesi adlandırabilir, dolayısıyla araç biraz farklı bir
metin döndürür — ve birincisini önbelleğe almış bir istemcinin elinde artık iki
metin vardır ve ikisini de sonraki her turda gönderir. Transkripti küçük tutmak
için var olan bir araç, transkript için yeni metin kaynağı olmamalı.

## Saklanan şey: yanıt, görünüm değil

Bu fazın tek kritik kararı. Saklanan, **numaralar** ve onları kimin adlandırdığı.
Basılmış metin asla — çünkü her boşluk işaretinin içinde tutamak yazılıdır
(`sift peek 9f2c41ab`), ve bir yakalamadan hatırlanan görünüm, başka bir
yakalamanın okuyucusunu **başkasının baytlarına** gönderirdi.

Testi bunu doğrudan kuruyor: aynı komutun iki ayrı yakalaması alınıyor, ikincisi
birincinin cevabıyla cevaplanıyor, ve `one.handle not in second.text`.

Numaralar zaten modelin gerçek cevabı; ondan sonrası aritmetik ve eldeki metne,
eldeki tutamak için yeniden yapılıyor. Böylece taze bir görünüm için doğru olan
hiçbir şey hatırlanmış görünüm için yanlış olmuyor.

## Anahtarda ne var, ne yok

Anahtar cevabı değiştirebilecek her şey: metin, soru, tavan, numaralamanın
başladığı yer. Bu yüzden geçersiz kılma kuralı yok — değişen dosya farklı bir
anahtardır ve eski kayıt bir daha hiç sorulmaz.

`keep` **bilerek yok**, ve bunu test yakalattı. İlk hâlinde anahtardaydı; test
`--keep` ile ikinci çağrının önbelleğe düşmesini bekledi ve düşmedi. Doğrusu şu:
`keep` modelin ne sorulduğunu ya da ne cevapladığını değiştirmiyor — desen burada,
bu satırlarda, yargı bittikten sonra eşleştiriliyor. Anahtara koymak, her farklı
`--keep`'in aynı yargıyı yeniden satın alması demekti; yani tam da bu fazın
durdurmak için var olduğu israf.

## Dürüstlük: hatırlanan görünüm söylüyor

Dipnot modeli adlandırmaya devam ediyor — yargı gerçekten onun. Yapmaması gereken
şey modelin **az önce sorulduğunu** ima etmek: istek harcayan bir aracı izleyen
okuyucu, hangi görünümlerin istek yediğini bilmeyi hak ediyor.

Ayrı bir alan taşınmıyor; çıkarım yeterli: model adı olan ve sıfır soruya mal
olan bir görünüm ancak önbellekten gelmiş olabilir. `(remembered)` bunu söylüyor.

## Testlerde varsayılan kapalı

`conftest.py` her test için `SIFT_CACHE=0` koyuyor, ve bu bir kolaylık değil,
bir zorunluluk. Buradaki testlerin neredeyse hepsi **soru sorulduğunda** ne
olduğunu ölçüyor: prompt'ta ne vardı, kaç ask sürdü, model erişilemeyince yedek
ne yapıyor. Sessizce cevap veren bir önbellek bunları hiçbir şeyin ölçümüne
dönüştürür — ve bunu **hata vermeden** yapar.

Ölçüldü: `test_the_name_of_a_file_plays_no_part_in_its_outline` aynı baytları iki
ad altında damıtıp modelin aynı şeyi gördüğünü sınıyor. Önbellek açıkken ikinci
çağrı hiç modele ulaşmıyor, yani karşılaştırmak için var olan şey hiç olmuyor.
Bu test kırıldığı için görüldü; kırılmasaydı görülmeyecekti.

Doğru şekil bu: önbellek, her testin sessizce altında koştuğu bir koşul değil,
kendi testleri olan bir özellik.

## Ölçü

- Aynı dosyaya iki `digest`: **2 istek → 1 istek**, ve iki metin bayt bayt aynı.
- Aynı çıktının iki ayrı yakalaması: ikincisi 0 ask, ve kendi tutamağını gösteriyor.
- `sift gc` artık kimsenin sormadığı yanıtları da unutuyor — yazıldığı zamana
  göre değil, **en son istendiği** zamana göre.
- Bu fazın beş kuralı da mutasyon bataryasında.
