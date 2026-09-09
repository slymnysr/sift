# İŞ 2 — Geliştirme planı

## Bu planın konusu

İŞ 1 sift'i **bulunabilir** yaptı. Bu iş sift'i **daha iyi** yapıyor.

Ayrım önemli: burada tek bir satır tanıtım yok. Her faz ya kodun içinde
doğrulanmış bir boşluğu kapatıyor, ya yazılı bir iddiayı sınanır hâle
getiriyor, ya da aracın zaten bildiği bir şeyi söylemesini sağlıyor.
Kanıtlar `BULGULAR.md`'de; bu dosya ne yapılacağını söylüyor.

## Kural

Üç kural esnemez — hiçbir faz onlara dokunmaz:

1. Gösterilen hiçbir satır uydurulmuş değildir
2. Hiçbir şey atılmaz
3. Hiçbir şey senin komutunu bozamaz

Ve bu planın kendi kuralı: **her faz kendi testini getirir.** Yeşil bir suite,
o kuralın korunduğunu değil, testlerin itiraz etmediğini söyler. Yeni bir kural
geldiğinde mutasyon bataryasına da bir satır düşer.

## Fazlar

| # | Faz | Ne biter | Neden | Durum |
|---|-----|----------|-------|---|
| G1 | Anahtar tek yol olmasın | Kendi uç noktanı gösterdiğinde anahtarsız çalışır | Bugün sift'i denemek için NVIDIA anahtarı şart — benimsemenin önündeki en büyük tek engel | **bitti** |
| G2 | Araçların künyesi | Yedi araç `annotations` + `title` taşır | `peek` bir dosya okur, `run` rastgele komut çalıştırır; istemci şu an ikisini ayırt edemiyor | **bitti** |
| G3 | Sonucun içinde veri | Metin aynı, yanında `handle`/`exit`/`shown`/`model` alanları | Ajan çıkış kodunu düzyazıdan çıkarmak zorunda kalmasın | bekliyor |
| G4 | Uzun komut sessiz kalmasın | `run` ilerleme bildirir | 5 dakikalık derleme şu an asılı görünüyor | bekliyor |
| G5 | Boru ve modül | `sift digest -`, `python -m sift` | İkisi de Unix'te ve Python'da beklenen yol; ikisi de yok | bekliyor |
| G6 | Diskin tavanı | Bir yakalamanın yazabileceği bir sınır, ve söylenmiş bir sınır | `sift run -- yes` bugün diski doldurur | bekliyor |
| G7 | Windows'ta ağacı bitirmek | `stop` orada da başlattığı her şeyi bitirir | README bunu iddia ediyor, Windows'ta sınanmıyor | bekliyor |
| G8 | Kazancı araç söylesin | `stats` kazanılan token'ı da basar | Araç cevabı biliyor ve basmıyor | bekliyor |
| G9 | Depo sağlığı | `SECURITY.md`, `CONTRIBUTING.md`, `uv.lock`, güncel action'lar | Depo halka açık ve araç kabuk komutu çalıştırıyor | bekliyor |
| G10 | Bataryayı uçtan uca | 182 mutasyonun tamamı bir kez koşar | Kaç kuralın korumasız olduğunu bilmiyoruz | bekliyor |

Sıra rastgele değil: G1 en çok kişiye dokunan, G2–G4 istemci tarafını
düzeltenler, G5–G8 aracın kendi eksikleri, G9–G10 projenin sağlığı.

---

## G1 — Anahtar tek yol olmasın

**Bulgu:** `available` yalnız anahtara bakıyor (`BULGULAR.md` A1). Yerel model
sunucularının hiçbiri anahtar istemez, ve hepsi OpenAI şeklinde konuşur.

**Yapılacak**
- `available`: anahtar **ya da** kullanıcının bilerek yazdığı `SIFT_BASE_URL`.
  Varsayılan uç nokta hâlâ anahtar ister — kural şu: *kendi sunucunu
  gösterdiysen kararı sen verdin*
- `NO_KEY` uyarısı ve 24. fazın MCP reddi bu yeni duruma göre okunmalı: kendi
  uç noktasını göstermiş biri "kurulumu bitmemiş" değildir
- Taklit bir OpenAI sunucusuna karşı uçtan uca test (`test/wire.py` şekli)
- README: Ollama / llama.cpp / vLLM / LM Studio için tam satırlar

**Bitti sayılır:** Anahtarsız, `SIFT_BASE_URL` verilmiş bir makinede
`sift run` modele soruyor ve bunu altbilgide söylüyor.

## G2 — Araçların künyesi

**Yapılacak** — yedi araca `annotations` ve `title`. Dürüst dolduruluşu:

| araç | read_only | destructive | idempotent | open_world |
|---|---|---|---|---|
| `run` | hayır | **evet** | hayır | evet |
| `follow` (stop'suz) | evet | hayır | hayır | evet |
| `tool` | hayır | hayır | hayır | evet |
| `outline`, `digest`, `digest_many` | evet | hayır | evet | evet |
| `peek` | evet | hayır | evet | **hayır** |

`open_world` çoğunda evet, çünkü hepsi bir modele soru gönderiyor. `peek`
göndermiyor — tek yerel araç o.

`run` için `destructive: true` yazmak reklamın tersi, ve doğrusu bu: araç
rastgele kabuk komutu çalıştırır.

**Bitti sayılır:** `tools/list` künyeleri döndürüyor, ve bir test bunu
gerçek taşıyıcı üzerinden okuyor.

## G3 — Sonucun içinde veri

**Yapılacak** — `structured_output`: metin **birebir aynı kalır** (üçüncü kural:
bugün çalışan bir istemci yarın da çalışmalı), yanına alanlar düşer:
`handle`, `exit`, `shown`, `total`, `model`, `cached`.

**Bitti sayılır:** Sonuçta hem eski metin hem alanlar var; bir test ikisinin
aynı şeyi söylediğini kanıtlıyor.

## G4 — Uzun komut sessiz kalmasın

**Yapılacak** — `run` çalışırken ilerleme bildirimi: kaç satır geldi, ne kadar
oldu. Bildirim gönderilemiyorsa hiçbir şey değişmez (üçüncü kural).

**Bitti sayılır:** Uzun bir komutta istemci ilerleme alıyor; bildirim yolu
kapalıyken sonuç birebir aynı.

## G5 — Boru ve modül

**Yapılacak**
- `sift digest -` ve `sift outline -`: standart girdiden oku
- `src/sift/__main__.py`: `python -m sift` = `sift`

**Bitti sayılır:** `journalctl | sift digest -` çalışıyor, `python -m sift`
kullanım metnini basıyor.

## G6 — Diskin tavanı

**Yapılacak** — bir yakalamanın yazabileceği tavan (`SIFT_MAX_CAPTURE`,
varsayılan cömert). Tavana varılınca **komut durdurulmaz** (üçüncü kural) ve
**yazılan silinmez** (ikinci kural); yalnız yeni bayt saklanmaz ve bu hem
altbilgide hem `peek`te söylenir.

**Bitti sayılır:** Tavanı aşan bir komut bittiğinde çıkış kodu kendisinin,
görünüm doğru, ve nerede durulduğu yazıyor.

## G7 — Windows'ta ağacı bitirmek

**Yapılacak** — Job Object: `CreateJobObject`,
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, `AssignProcessToJobObject`,
`TerminateJobObject`. 27. faz Windows için ctypes'ı zaten kullandı.

Bu makine WSL; sınama **CI'da windows-latest üzerinde** yapılacak — 27. fazda
olduğu gibi, hataları CI gösterecek.

**Bitti sayılır:** Windows'ta atlanan beş testin ağaç bitirmeye bakanları
koşuyor ve yeşil; ya da yapılamadıysa README'deki iddia platform adıyla
sınırlandırılıyor. **İkisinden biri şart** — sınanmamış bir iddia kalamaz.

## G8 — Kazancı araç söylesin

**Yapılacak** — `stats` bir sütun daha: kazanılan token. Kaynak uydurma değil,
uç noktanın soruda saydığı `prompt_tokens`. Sayılmamış koşu sayılmamış kalır
ve öyle görünür (23. fazın reddi aynen durur).

**Bitti sayılır:** `stats` kazancı ölçülmüş sayıyla basıyor, ölçülmemişi
`—` ile.

## G9 — Depo sağlığı

**Yapılacak**
- `SECURITY.md`: bu araç kabuk komutu çalıştırır ve dışarı metin gönderir;
  neyin gönderildiği, nasıl kapatılacağı, açık nasıl bildirilir
- `CONTRIBUTING.md`: notlar Türkçe, kod ve yorumlar İngilizce, her kural bir
  mutasyon — yabancıya haritayı ver
- `uv.lock` izlemeye alınır: CI önbelleği bugün hiç geçersizleşmiyor
- `actions/checkout@v5`, `astral-sh/setup-uv@v7` (Node 20 uyarısı)

**Bitti sayılır:** CI'da Node 20 ve önbellek uyarıları yok, üç dosya yerinde.

## G10 — Bataryayı uçtan uca

**Yapılacak** — 182 kuralın tamamı bir kez. ~3,5 saat; arka planda koşar.
Kaçan her kural ya bir test kazanır ya da kuralın gerçekten korunmadığı
yazılır.

**Bitti sayılır:** Tam koşunun çıktısı `gelistirme/` altında, kaçanlar
adlarıyla listelenmiş ve her biri için ne yapıldığı yazılmış.
