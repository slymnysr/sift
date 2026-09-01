# Faz 7 — MCP sunucusu

## Fazın cümlesi

Terminalde kısaltılmış bir görünüm birine kaydırma zahmeti kazandırır. MCP
üzerinden **bağlam penceresi** kazandırır — ve bir araç sonucu, kendisinden
sonraki **her turda yeniden gönderilir**. Yani konuşmaya girmeyen 5.000 satırlık
bir günlük bir kez ödenmemiş olmuyor; konuşmanın geri kalanı boyunca ödenmemeye
devam ediyor.

Planın ilk cümlesi ("her turda yeniden gönderilir") bu faza kadar bir iddiaydı.
Bu fazla birlikte bir arayüz.

## 657 satır ve 7 araç, 155 satır ve 3 araca indi

winnow'un `server.py`'si 657 satır ve yedi araç açıyordu: `run`, `digest`,
`follow`, `peek`, `stats`, `memory`, `tool`. sift üç açıyor: **`run`, `outline`,
`peek`**. Hiçbiri sessizce düşmedi:

| winnow aracı | sift'te | neden |
|---|---|---|
| `run` | `run` | aynı iş |
| `digest` | `run` | winnow'da damıtmayı yeniden çalıştırmak ayrı bir araçtı; sift'te `run` zaten damıtılmış döner, damıtılmamış bir hâli hiç yok |
| `peek` | `peek` | aynı iş, artık dosya yollarını da alıyor |
| — | `outline` | Faz 6'nın ürünü. winnow'da bu bir kütüphane fonksiyonuydu, araç değildi |
| `stats` | — | **Faz 8**: kazanç raporu o fazın konusu |
| `memory`, `tool` | — | winnow'a özgü, sift'in üç kuralında karşılığı yok |
| `follow` | — | **gerçek eksik**, aşağıda |
| (`sift list`) | — | **Faz 10**, aşağıda |

## `sift list` neden araç değil

Komut satırında dört komut var, sunucuda üç araç. Eksik olan `list`, ve bu bir
unutma değil.

`sift list` bu makinede son çalıştırılan komutları döner — modelin hiç
istemediği, hatta hiç haberi olmayan komutlar dâhil. Bu, "makineden ne çıkıyor"
sorusudur ve cevabı Faz 10'a aittir. Araç eklemek kolaydır; bir istemcinin
alışkanlık edindiği aracı geri almak zordur.

## Gerçek eksik: arka plan komutları

winnow'da `run(background=true)` ve `follow` vardı: biten değil, **bitmeyen**
komutlar için — dev sunucusu, `docker compose up`, günlük kuyruğu. `follow` son
sorulduğundan beri basılanları döndürüyordu.

sift'te bunun karşılığı yok. Hedef "var olan özellikleri tümüyle" diyor, bu
yüzden sessizce düşürmüyorum: plana **9. satır** olarak eklendi ve sonrakiler
birer kaydı. Yayından (artık 11) önce kapanması gereken bir açık.

## İki ön yüz, tek merdiven

`_view` ve `_outline_view` cli.py'de özel fonksiyonlardı: modele sor, olmazsa
yedeğe düş, her hâlükârda okunacak bir şey döndür. Sunucunun da tam olarak bu
merdivene ihtiyacı var.

Kopyalamak yerine `src/sift/view.py`'ye taşındı — ve alt bilgi satırlarını üreten
üç fonksiyon da onunla beraber. Sebebi biçimsel değil:

> Birinde olup diğerinde olmayan bir geri-düşme, üçüncü kuralın terminalde
> geçerli olup telde geçerli olmaması demektir; bu da hiç geçerli olmaması
> demektir.

Bunun kanıtı mutasyonda. `view.py`'deki tek bir satırı bozduğunda **hem CLI hem
sunucu testi** düşüyor. İki kopya olsaydı biri çürürken diğeri yeşil kalırdı ve
batarya bunu göremezdi.

Taşımanın maliyeti de ölçüldü: cli.py 9.445 bayttan 7.224 bayta indi, ve **üç
mutasyon çapası kırıldı** — hedefledikleri satırlar artık başka dosyadaydı.
Batarya bunu "NO ANCHOR" diye bildirir. Kod taşımanın sessiz maliyeti budur.

## stderr yok

Komut satırı alt bilgiyi stderr'e yazar: hangi tutamak, komut nasıl bitti, satır
sayısı, ve **satırları bir model mi seçti**. Bir MCP istemcisi stderr görmez.

Bu satır düşerse, istemci modelin seçtiği bir görünümle hiçbir modele
ulaşılamadığı için gösterilen dosya uçlarını ayırt edemez — ve ikincisini
birincisi sanır. Yanlış bir satır göstermekten farklı ama aynı ölçüde ciddi:
gösterilenin **ne olduğu** hakkında yanlış bilgi.

Bu yüzden alt bilgi sonucun içinde yolculuk ediyor. Terminalde dürüst olan şey
telde de dürüst; sadece aynı dizgenin içinde seyahat etmesi gerekiyor.

## İstisna da yok

Bir araç `raise` ederse istemciye protokol hatası gider ve modelin eline hiçbir
şey geçmez — üçüncü kuralın engellemek için var olduğu tek sonuç. Okunamayan
dosya, olmayan tutamak, başlatılamayan komut: hepsi `sift: ...` diye başlayan bir
**cümle** olarak döner.

Model, okuyucunun makine olması yüzünden daha az bilgi almıyor.

## Ölçüm: uçtan uca, canlı

Faz 8 kazanç raporunun fazı; buradaki sayı kıyas değil, zincirin bütününün
çalıştığının kanıtı — gerçek bir komut, gerçek bir model, gerçek bir boru:

İki komut, kurulu `sift-mcp` alt süreç olarak başlatıldı, gerçek stdio borusu,
gerçek model. Ölçen dosya `test/wire.py`.

**Aracın yazıldığı iş — geçen bir test suiti:**

| | |
|---|---|
| komut | `python -m pytest --no-header -vv` |
| yakalanan | 378 satır · 42.492 bayt |
| dönen | 5 satır · 827 bayt · **%1,9** |
| uydurulan | **0** |
| model | `nemotron-3-super-120b-a12b` |

Dönen görünümün tamamı:

```
─ 337 lines not shown · sift peek 3f235a10 for any of them ─
test/test_model.py::test_an_unreadable_timeout_falls_back_instead_of_failing PASSED [ 89%]
test/test_model.py::test_the_bridge_really_reaches_nvidia SKIPPED (g...)        [ 90%]
test/test_outline.py::test_the_name_of_a_file_plays_no_part_in_its_outline PASSED [ 90%]
─ 35 lines not shown · sift peek 3f235a10 for any of them ─
test/test_server.py::test_a_real_client_is_given_a_sentence_and_not_a_crash PASSED [100%]
─ 1 line not shown · sift peek 3f235a10 for any of them ─
======================= 372 passed, 1 skipped in 11.51s ========================
```

Okunması gereken satır — sondaki özet — duruyor. Boşluklar kaç satırı örttüğünü
söylüyor. Gösterilen 5 satırın 5'i de yakalamada var.

**Ve fazın ölçümünün açığa çıkardığı sınır — 10.000 satırlık bir yakalama:**

| | |
|---|---|
| komut | `ruff check --select ALL --no-cache .` |
| yakalanan | 9.984 satır · 547.705 bayt |
| dönen | 2.842 satır · 181.469 bayt · **%33,1** |
| uydurulan | **0** |
| model | `nemotron-3-ultra-550b-a55b` |

Hiçbir kural çiğnenmedi: dönen her satır yakalamada var, hiçbiri uydurulmamış,
`peek` gerisini geri veriyor. Ama 181 KB bir bağlam penceresine sokulacak miktar
değil — bu boyutta araç kendi vaadini tutmuyor.

Sebep tahmin değil, kodun kendi yorumunda yazılı (`distill.py:51`):
*"a long build is split and the answers are added together."* `CHARS_PER_ASK`
120.000 karakter; 547 KB'lık yakalama beş pencereye bölünüyor ve **her pencere
kendi payını tutuyor**. Pencereler arasında bütçe yok, dolayısıyla dönen satır
sayısı girdiyle birlikte doğrusal büyüyor.

Bu, planın 8. satırının ("Bütçe ve ölçüm") tam konusu ve orada kapanacak. Burada
kaydedilmesinin sebebi bu fazın ölçümüyle bulunmuş olması: 378 satırda görünmeyen
şey 9.984 satırda görünüyor. Küçük örneklerle ölçmek, ölçmemektir.

## Testler

18 yeni test, toplam 373. İkisi fazın omurgası:

- **`test_the_installed_server_answers_over_stdio`** — kurulu `sift-mcp` konsol
  betiğini alt süreç olarak başlatır ve gerçek boru üzerinden konuşur. Dosyadaki
  diğer her test modülü doğrudan import eder; paketleme, giriş noktası ya da bir
  import yanlışsa bunu **yalnız bu test** görür.
- **`test_and_the_test_above_would_have_noticed`** — "mcp kurulu değilken sift
  çalışır" testinin dişli olduğunu kanıtlar. Engelin gerçekten engellediğini
  göstermezsen, o test her koşulda yeşil kalan bir süstür.

Bir de fazın yapısal iddiasını sınayan test var:
`test_the_server_climbs_the_same_ladder_as_the_command_line` — `view.py`'deki
damıtıcıyı kırar ve sunucunun terminalle **aynı** şekilde yedeğe düşmesini
bekler. Sunucunun kendi merdiveni olsaydı bu test yeşil kalırken gerçek olan
çürürdü.

Hepsi anahtarsız ve ağsız koşuyor: ölçülen şey taban, yani hiçbir modele
ulaşılamadığında sunucunun ne verdiği.

## Mutasyonlar

49'dan **55'e** çıktı, **55/55 yakalandı**.

Ama asıl bulgu sayıda değil: `view.py`'ye taşınan kod **üç mutasyonun çapasını
kırdı**. Hedefledikleri satırlar artık cli.py'de değildi; batarya bunları
"NO ANCHOR" diye bildirir ve kaçak sayar. Yeşil bir suit bunu göremezdi —
testler zaten geçiyordu, kırılan şey testin *dişiydi*.

Yeni altısı fazın altı kuralını hedefliyor: alt bilginin sonucun içinde
yolculuk etmesi, tek alt bilginin iki ön yüze birden hizmet etmesi, istemciden
gelen komut satırının borularıyla birlikte komut satırı olması, okunamayan
dosyanın ve başlatılamayan komutun cümle olarak dönmesi, ve açılan her aracın
istemin içinde adının geçmesi.

## Sırada

**Faz 8 — Bütçe ve ölçüm.** Sıralama bu fazın ölçümüyle değişti: eksik bir
özellik (arka plan komutları) 9. satıra kaydı, çünkü **ölçekte kırılan bir
vaat, hiç olmayan bir özellikten daha acildir**. 9.984 satırlık bir yakalamanın
%33'ünü geri veren araç, bağlam penceresini korumak için var olduğunu
söyleyemez.
