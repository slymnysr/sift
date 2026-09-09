# G4 — Uzun komut sessiz kalmasın

**Tarih:** 9 Eylül 2026 · **Durum:** bitti

## Sorun

On dakikalık bir derleme, bir borunun ucundan bakınca asılı kalmış bir
sunucudan ayırt edilemez. Sessizliği izleyen bir istemcinin vazgeçme hakkı
vardır — ve MCP, bir ilerleme bildiriminin o sayacı **sıfırlamasına** izin
verir. Yani bu, süslemeden ibaret değil: uzun bir komutun çalışması ile zaman
aşımına uğraması arasındaki fark.

## Neden G3 hayır, G4 evet

İkisi de "sonuca bir şey ekleyelim" gibi duruyor. Değiller, ve fark ölçülebilir:

| | nereye gider | modele maliyeti |
|---|---|---|
| G3 `structuredContent` | sonucun **içine** | +51 token, %39,5 |
| G4 ilerleme bildirimi | sonucun **yanına** | **sıfır** |

Bildirim istemciye gider, konuşmaya değil. Bağlam penceresine tek bayt
girmiyor. Bu yüzden biri reddedildi, öbürü yapıldı.

## Yapılan

`run` artık bir eşyordam. Engelleyen iş bir iş parçacığında koşuyor, yanında
beş saniyede bir "hâlâ çalışıyor, 35 sn oldu" diyen bir sayaç var.

Beş saniye: her makul sabrın içine düşecek kadar kısa, bir saat süren bir
komutun 3.600 değil 720 bildirim göndereceği kadar uzun.

Üçüncü kural bu fazın her satırında görünüyor:

- Bağlam yoksa (doğrudan çağrı, dinlemeyen istemci) **sayaç hiç kurulmuyor**,
  iş olduğu gibi yapılıyor
- Sayacın kendi hatası olduğu yerde yutuluyor — istemciyle konuşmak, bir
  soketin bozulabileceği her şekilde bozulabilir, ve hiçbiri çağıranın
  cevabına mal olamaz
- İş ne olursa olsun döndürülüyor; `finally` yalnız sayacı iptal ediyor

## Bataryanın yakaladığı şey

İlk yazdığım "kırık ilerleme bedava" testi **hiçbir şey kanıtlamıyordu.**
Komut `print(1)` idi ve ilk kalp atışından önce bitiyordu: kırık bağlam hiç
çağrılmıyordu, test yeşildi.

Bunu test bulmadı, **mutasyon buldu**: `suppress(Exception)` → `suppress(ValueError)`
mutasyonu ESCAPED döndü. Test artık hem komutu kalp atışından uzun tutuyor hem
de kırık çağrının gerçekten yapıldığını iddia ediyor.

Bu, `mutations.py`'nin baştaki cümlesinin üçüncü örneği: *"Twice already in
this project a test passed while proving nothing."* Artık üç.

## Testler

| test | ne kanıtlıyor |
|---|---|
| `a_command_that_is_still_running_says_so` | Sayaç çalışıyor, geri saymıyor, cevap yine geliyor |
| `a_heartbeat_that_fails_costs_nothing` | Üçüncü kural, en kolay kazara kırılacağı yerde |
| `a_direct_call_with_nobody_listening_still_answers` | Bağlamsız çağrı |
| **`the_progress_reaches_a_real_client`** | **Kabloyu** kanıtlayan tek test |

Sonuncusu olmadan diğer üçü bir şey ifade etmezdi: hepsi `run`'a kendi
uydurdukları bağlamı veriyor. Kütüphane gerçek bir bağlamı hiç enjekte
etmeseydi — açıklama yanlış olduğu için, ya da isteğe bağlı parametreler
enjekte edilmediği için — üçü de yeşil kalır, hiçbir istemci tek bildirim
duymazdı.

## Yan etki: testler `await` istiyor

`run` eşyordam olunca ona doğrudan seslenen 15 test çağrısı `await` istedi ve
9 test `async def` oldu. `asyncio_mode = "auto"` sayesinde bu mekanikti.
`test_setup.py`'deki karışık liste (biri eşyordam, altısı değil) küçük bir
yardımcıyla çözüldü — beklemesi gerekiyorsa beklenir.
