# 24 — Anahtar: kurulumu bitmemiş makine

**Nereden çıktı:** Kullanıcı isteği. "Her indiren veya kuran kullanıcı kendi
NVIDIA anahtarını girmelidir; anahtar yoksa MCP'ye erişim olmamalı, uyarı
belirgin olmalı, ama modelin kendi çalışmasını bozmamalı."

## Üç durum, ikisi karıştırılıyordu

| Durum | Ne demek | Ne yapılmalı |
|---|---|---|
| `SIFT_NO_MODEL=1` | Kullanıcı bilerek kapatmış | Çalış, sus. Bu bir karar |
| Anahtar hiç yok | Kurulum bitmemiş | **Reddet / bağır** |
| Anahtar var, uç nokta düşmüş | 3. kuralın alanı | Yedeğe düş |

Bunlardan ikincisi, öncesinde birinciyle aynı muameleyi görüyordu: dipnotta beş
sessiz kelime — `no model (no api key)` — ve devam.

## Neden iki çağıran farklı cevap alıyor

Bu fazın tek gerçek kararı bu, ve 3. kuralı esnetmiyor; **kimin okuduğunu**
soruyor.

**Terminaldeki insan:** komut çalışır, baytlar durur, çıkış kodu döner. İlk 10 +
son 40 satırdan kurulmuş bir görünüm görür — ve *görebilir*. İyi olmadığını
anlar, `peek` yapar, anahtarını ekler. Ona sadece durumu söylemek yeter, ama
**yüksek sesle**: sessiz bozukluk, bozuk olmayan bir şeye benziyor.

**MCP'deki model:** görebileceği bir şey yok. Eline kısa bir metin ve
güvenmemesi için sebebi olmayan bir dipnot geçiyor. Sessizce daha kötü bir cevap,
bu projenin **kontrol edemeyecek bir okuyucuya** vermeyeceği tek şey.

O yüzden sunucu reddediyor. Ama reddetmek bozmak değil: araç bir cümle
döndürüyor, hata fırlatmıyor, ve komutu **hiç çalıştırmadığını** açıkça
söylüyor — ajan kendi kabuğuyla devam ediyor. En kötü sonuç "sift reddetti"
değil, "sift reddetti ve ajan fark etmedi" olurdu.

`peek` kapının dışında: model gerektirmiyor, dosya okuyup basıyor.

## Ne söylüyor

Uyarının içinde eyleme dönüşecek her şey var: anahtarın konabileceği üç yer,
nereden alınacağı (ücretsiz), bu arada ne yapılacağı, ve bilerek modelsiz
çalışmak isteyenin ne yazacağı. **Ne yapılacağını söylemeyen uyarı, vicdanı olan
gürültüdür.**

## Testlerin de söylemesi gerekti

Yan etki, ve öğreticiydi: `test_server.py` bilerek anahtarsız koşuyordu ve
"model erişilemezken taban ne verir"i ölçüyordu. Yeni kapı onu reddetti ve 18
test kırıldı.

Kırılmaları doğruydu. O testler *modelsiz* çalışmayı ölçüyor, *kurulmamış*
makineyi değil — ve ikisi artık farklı şeyler. `conftest.py` tüm suite için
`SIFT_NO_MODEL=1` koyuyor: suite bilerek modelsiz koşuyor ve artık bunu
**söylüyor**. `test_model.py` geri açıyor, çünkü o dosya sormanın kendisi
hakkında.

Bu, aynı oturumda üçüncü kez aynı şekle geldi: depo sızıntısı, ağa çıkan
testler, ve şimdi bu. Üçünde de düzeltme "bir sonraki dosyada unutma" değil,
`conftest.py`'de "unutmak mümkün değil" oldu.

## Ölçü

- Öncesi: anahtar yokken MCP araçları çalışıyor ve dipnotta beş kelimeyle
  durumu söylüyordu.
- Sonrası: modele bağlı **altı araç** reddediyor ve ne yapılacağını yazıyor;
  `peek` çalışmaya devam ediyor; komut satırı çerçeveli bir afiş basıyor ve
  komutu yine çalıştırıyor.
- 16 yeni test, 3 mutasyon.
