# Faz 6 — Dosya taslağı

`src/sift/outline.py`, `test/korpus-kaynak/`, `test/test_kaynak.py`,
`test/outlines.py`; `src/sift/distill.py`, `src/sift/peek.py`, `src/sift/cli.py`
değişti.

Faz 5 insan dilini sordu: bir günlük Vietnamca yazılmışsa seçim bozuluyor mu?
Bu faz aynı sorunun daha zor yarısını soruyor: dosya **hangi programlama
dilinde** yazılmışsa yazılsın, `sift` neyin bildirim olduğunu bulabiliyor mu —
üstelik kodun hiçbir yerinde programlama dillerinin var olduğuna dair tek satır
yokken?

Eski tasarımın bu soruya bir cevabı vardı ve o cevap bu projenin neden baştan
yazıldığının en somut örneği.

## Değiştirilen tasarım: 1099 satırlık tablo

`winnow`'da taslak çıkarma işini `src/winnow_mcp/outline.py` yapıyordu:

```
1099 satır
  84 dil girdisi (Language: suffixes, defines, imports, attaches, comment, names)
 260 uzantı/dosya-adı anahtarı
```

Her girdi, o dilde bir bildirimin nasıl göründüğünü anlatan düzenli ifadeler
tutuyordu. Dosya geldiğinde önce uzantısına bakılıyor, tabloda karşılığı
bulunuyor, sonra o dilin `defines` ifadesi satırlara uygulanıyordu.

İki kusuru vardı ve ikisi de kapatılabilir değildi.

**Birincisi, tablo hiç bitmiyordu.** 84 dil, dünyada kullanılan dillerin küçük
bir kısmı. Geçen hafta çıkan bir dil, bir şirketin içinde kalan bir DSL, uzantısı
olmayan bir yapı dosyası — hiçbiri tabloda yok, hiçbiri olmayacak da. Bir sonraki
kullanıcının 85. girdiyi istemesi kesindi.

**İkincisi, tablo doğru diller için bile yanlış çalışıyordu.** Bunu bize dışarıdan
kimse söylemedi; dosyanın kendi yorumu söylüyordu:

> *the rules are shapes, not grammars.*

Düzenli ifade bir imzanın **şeklini** tanır, dilbilgisini değil. `def` ile
başlayan her satır bir Python fonksiyonu değildir; bir dizgenin içinde de olabilir.
Haskell'de bir bildirimi başlatan hiçbir anahtar sözcük yoktur, sadece `::`
vardır — ve `::` C++'ta başka bir şeydir. Make'te bildirimi belirleyen şey
satırın **sekmeyle** başlayıp başlamamasıdır. Lisp'te ise ne uzantı ne şekil
yeter; `defn` ile `defprotocol` arasındaki farkı ancak okuyan bilir.

## İki soru, tek motor

Faz 6'nın asıl bulgusu şu: `distill`'in makinesi **sorudan bağımsız**.
Numaralandır, pencerelere böl, sor, cevaptan sayıları ayıkla, satırları
dosyadan bas. Bu zincirin hiçbir halkası "bu bir günlüktür" bilgisine dayanmıyor.

Bu yüzden `distill.py`'den `select()` çıkarıldı:

```python
def select(lines, question, handle, bridge=None) -> View | None
```

Şimdi iki soru var, tek motor:

| soru | nerede | ne sorar |
|---|---|---|
| `distill.QUESTION` | `distill.py` | ne bozuldu, ne uyardı, ne değişti |
| `outline.QUESTION` | `outline.py` | dosya neyi bildiriyor |

Cevap biçimini anlatan cümle (`ANSWER_FORMAT`) ikisinde de ortak ve tek bir
yerde duruyor — çünkü cevabı okuyan ayrıştırıcı da tek. İkinci bir soru, ikinci
bir motor değil; ikinci bir cevap biçimi hiç değil. Test bunu doğrudan
doğruluyor: her iki sorunun da `ANSWER_FORMAT` ile bittiği kontrol ediliyor.

Sonuç, satır sayısıyla:

```
winnow/outline.py   1099 satır   (84 dil girdisi + düzenli ifadeler)
sift/outline.py       91 satır   (24 satırı, tablonun neden gittiğini anlatan belge)
```

Kalan 67 satırın içinde tek bir dil adı, tek bir uzantı, tek bir düzenli ifade
yok.

## İstemde dosya adı yok

Bu, fazın taşıyıcı kararı ve testi.

`outline(path)` modele **sadece numaralandırılmış dosya içeriğini** gönderir.
Yol da, dosya adı da, uzantı da isteme girmez. Yol yalnızca `View.handle` olarak
saklanır; boşluk işaretçisinin geri dönüş yolunu yazabilmesi için.

Bunun iki sonucu var:

- **Aynı baytlar her zaman aynı taslağı verir.** `a.py`, `b.rs`, `c.qqzz`,
  `Makefile` ve `d` adlarıyla yazılan aynı içerik beş kez sorulduğunda tek bir
  istem üretiliyor. Bir uzantı tablosu bu testten sağ çıkamaz. Bir dosya-adı
  tablosu da çıkamaz: `Makefile`, eski tasarımın adıyla tanıdığı girdilerden
  biriydi, burada `d` adlı dosyayla birebir aynı cümlelerle soruluyor.
- **Dizin yapısı modele sızmıyor.** `src/musteri/odeme_saglayici.py` yolu, tek
  başına bir şirketin neyi nasıl kurduğunu anlatır. Bu, Faz 9'un (gizlilik)
  konusu ama kararı burada verildi: gönderilmeyen veri, maskelenmesi gerekmeyen
  veridir.

## Bütçe: istenir, dayatılmaz

`BUDGET = 120` istemin içinde geçer, kodda hiçbir yerde uygulanmaz.

Uzun gelen bir cevabı kırpmak, hangi bildirimin daha az önemli olduğuna karar
vermek demek. Dili okumadan bu kararı vermek, tam da bu dosyanın var olma
sebebi olan tahmin: "iç içe olan" ne demek? Bir dilde girinti, ötekinde süslü
parantez, üçüncüsünde hiçbiri. Uzun gelen taslak zaten görünür — görünüm kaç
satırdan kaçını tuttuğunu yazıyor. Sessizce kırpılan taslak görünmez.

## Korpus

14 örnek, 8 sözdizim ailesi, 556 satır. **Hepsi `.txt` uzantısıyla duruyor.**

Bu düzen kaygısı değil, ölçümü dürüst yapan şey: Rust örneği `.rs` adıyla
dursaydı, Rust okuyan bir modelle `.rs` tanıyan bir tabloyu birbirinden
ayıramazdık. `.txt` altında uzantı tablosu **sıfır** alır; sıfırın üstündeki her
puan dosyanın okunmasıyla kazanılmıştır.

| örnek | dil | aile | satır | bildirim | gövde |
|---|---|---|---:|---:|---:|
| clojure-rapor | clojure | parens | 31 | 9 | 13 |
| cpp-baslik | cpp | braces | 35 | 12 | 0 |
| elixir-onbellek | elixir | end | 40 | 8 | 7 |
| go-kuyruk | go | braces | 50 | 8 | 15 |
| haskell-ayristirici | haskell | equations | 44 | 7 | 16 |
| hcl-altyapi | hcl | declarative | 44 | 7 | 0 |
| java-depo | java | braces | 48 | 8 | 9 |
| makefile-yapi | make | declarative | 27 | 11 | 6 |
| python-akis | python | indent | 46 | 6 | 20 |
| qqzz-uydurma | qqzz | invented | 35 | 6 | 17 |
| ruby-fatura | ruby | end | 37 | 10 | 8 |
| rust-matris | rust | braces | 42 | 8 | 14 |
| shell-dagitim | shell | functions | 40 | 9 | 13 |
| sql-sema | sql | declarative | 37 | 7 | 10 |
| **toplam** | **14 dil** | **8 aile** | **556** | **116** | **148** |

Taban, dil sayısına değil **aile** sayısına konuldu. Haskell'de, Make'te ve
Lisp'te bir bildirim, Java'da bir bildirime düzenli ifadenin paylaşabileceği
hiçbir şekilde benzemez. On dört dilin altı ailede dağılması, tablonun daha uzun
bir tabloyla değiştirilemez olduğu noktadır.

`qqzz-uydurma` bu korpusun en önemli örneği. Hiçbir derleyicisi, hiçbir belgesi,
hiçbir yerde girdisi olmayan, bu korpus için uydurulmuş bir dil:

```
tanim Dugum <ad: yazi, agirlik: sayi>
islem enkisa(bas: Dugum, son: Dugum) -> liste<Kenar>
sabit VARSAYILAN_MALIYET = 1
olay dugum_eklendi(d: Dugum)
```

Kimse `tanim`ın ne demek olduğuna bakamaz — bu testi yazan da dâhil. Taslak
buradan bir şey çıkarıyorsa okuyarak çıkarmıştır.

## Bildirim satırı ölçütü

Faz 5'in ölçütü buraya uyarlandı:

> Bir satır, o satır olmadan kişi **dosyanın ne içerdiğini** söyleyemiyorsa
> taslakta zorunludur.

Ölçüt üç kümeye ayırıyor. **Zorunlu**: dosyanın sunduğu bir şeyi adlandıran
satır. **Gövde**: bir tanımın içindeki ifadeler — taslakta işi yok. **Bağlam**:
ne biri ne öteki; model gösterirse ceza yok, göstermezse eksik sayılmaz.

İlk etiketleme turunda 31 satır yanlış tarafa konmuştu ve **ölçümden önce**
düzeltildi:

| indirilen | neden |
|---|---|
| `son islem`, `son tanim`, `son olay` (5) | kapanış satırı hiçbir şeyi adlandırmaz |
| `@Override`, `@Repository`, `@Transactional`, `@impl true`, `@dataclass(...)` (9) | bildirimi süsler, adlandırmaz |
| `template <typename T>`, `RETURNS NUMERIC AS $$`, `( Belirtec(..)` ve dışa aktarım listesi, `= Sayi Double` ve veri kurucuları, `(:require ...)` (14) | devam satırı; adı bir üst satır koydu |
| `lifecycle {`, `versioning_configuration {`, `required_providers {` (3) | kaynağın ayarı, dosyanın sunduğu şey değil |
| `.PHONY: ...` (1) | hedefleri adlandırmaz, onlar hakkında bir şey söyler |
| `defp gecerli?(_deger), do: true` (1) | çok koşullu tanımın ikinci koşulu; ilki zaten adlandırdı |

155 → 140 düzeltmesi Faz 5'te ölçümden **sonra** yapılmıştı ve orada da doğruydu,
çünkü satırlara uygulanmıştı puanlara değil. Burada sıra tersine çevrildi:
düzeltme sonuçlar görülmeden yapıldı, çünkü kaçırılan satırları gördükten sonra
cetveli oynatmak, cetveli sonuca uydurmaktır.

## Ölçüm

Üç koşu, 14 örnek, 42 taslak, 348 bildirim fırsatı.

| koşu | bildirim | gövde | korpusun gösterilen kısmı | model |
|---|---|---|---|---|
| 1 | 109/116 | 45/148 | 292/556 (%52) | ultra + super |
| 2 | 108/116 | 51/148 | 316/556 (%56) | ultra |
| 3 | 115/116 | 54/148 | 315/556 (%56) | ultra + super + lightning |
| **toplam** | **332/348 (%95,4)** | | | |

Örnek bazında, üç koşu nokta ile ayrılmış:

| örnek | aile | bildirim | gövde | gösterilen |
|---|---|---|---|---|
| clojure-rapor | parens | 9 · 2 · 9 / 9 | 7 · 0 · 13 / 13 | 19 · 4 · 31 / 31 |
| cpp-baslik | braces | 6 · 12 · 12 / 12 | 0 · 0 · 0 / 0 | 8 · 23 · 22 / 35 |
| elixir-onbellek | end | 8 · 8 · 8 / 8 | 0 · 0 · 0 / 7 | 14 · 14 · 14 / 40 |
| go-kuyruk | braces | 8 · 8 · 8 / 8 | 0 · 0 · 0 / 15 | 18 · 22 · 18 / 50 |
| haskell-ayristirici | equations | 7 · 7 · 7 / 7 | 16 · 16 · 4 / 16 | 39 · 38 · 22 / 44 |
| hcl-altyapi | declarative | 7 · 7 · 7 / 7 | 0 · 0 · 0 / 0 | 38 · 44 · 38 / 44 |
| java-depo | braces | 8 · 8 · 8 / 8 | 9 · 9 · 9 / 9 | 48 · 48 · 48 / 48 |
| makefile-yapi | declarative | 11 · 11 · 11 / 11 | 0 · 0 · 0 / 6 | 12 · 12 · 12 / 27 |
| python-akis | indent | 5 · 5 · 5 / 6 | 0 · 0 · 1 / 20 | 11 · 10 · 13 / 46 |
| qqzz-uydurma | invented | 6 · 6 · 6 / 6 | 3 · 3 · 3 / 17 | 11 · 14 · 11 / 35 |
| ruby-fatura | end | 10 · 10 · 10 / 10 | 0 · 0 · 0 / 8 | 10 · 10 · 11 / 37 |
| rust-matris | braces | 8 · 8 · 8 / 8 | 0 · 0 · 14 / 14 | 15 · 15 · 37 / 42 |
| shell-dagitim | functions | 9 · 9 · 9 / 9 | 0 · 13 · 0 / 13 | 12 · 31 · 9 / 40 |
| sql-sema | declarative | 7 · 7 · 7 / 7 | 10 · 10 · 10 / 10 | 37 · 31 · 29 / 37 |

**11 örnek üç koşunun üçünde de tam puan aldı.** Toplam 16 kaçık var ve hepsi
üç yerde toplanıyor: `cpp-baslik` 1. koşuda (6), `clojure-rapor` 2. koşuda (7),
`python-akis` satır 27 üç koşuda da (3).

### Sonuç: tablonun asla yapamadığı aileler, yapabildiklerinden iyi

Aile bazında, üç koşunun toplamı:

| aile | bildirim | düzenli ifadeyle yapılabilir miydi? |
|---|---|---|
| declarative | 75/75 | kısmen |
| end | 54/54 | zor |
| functions | 27/27 | kısmen |
| equations | 21/21 | **hayır** |
| invented | 18/18 | **hayır** |
| parens | 20/27 | zor |
| braces | 102/108 | **evet** |
| indent | 15/18 | evet |

Ayırıp toplarsak:

```
düzenli ifadenin iyi olduğu aileler (braces + indent)   117/126   %92,9
düzenli ifadenin zorlandığı ya da hiç yapamadığı aileler 215/222   %96,8
```

Bu, fazın taşıdığı sayı. 1099 satırlık tablonun tuttuğu şeyler — süslü parantez
ve girinti — modelin **en kötü** olduğu yer; tablonun hiç tutamadığı şeyler —
Haskell denklemleri, Make hedefleri, Lisp formları ve hiçbir yerde girdisi
olmayan uydurma dil — modelin en iyi olduğu yer. Örnek sayıları eşit değil ve
`braces` puanını tek bir kötü koşu (cpp, 1. koşu) aşağı çekiyor; ama işaret
tersine dönecek kadar zayıf değil: tabloyu silmek, tablonun kapsadığı dillerde
bile bir şey kaybettirmedi.

`qqzz-uydurma` üç koşuda da **6/6**. Derleyicisi, belgesi, hiçbir yerde girdisi
olmayan bir dilin bildirimleri, üç kez üst üste eksiksiz bulundu.

### Faz 5'ten gerçek bir davranış farkı: oynama artık bildirimlere de vuruyor

Faz 5'te modelin kararsızlığı **yalnız gürültü tarafındaydı**: `docker-ar` üç
koşuda 24/17/18 satır gösterdi ama zorunlu 9 satırın hepsini her koşuda verdi.
Model neyin önemli olduğunda değil, ne kadar bağlam ekleyeceğinde kararsızdı.

Taslakta bu ayrım korunmuyor. 14 örneğin 12'si üç koşuda da aynı bildirim
sayısını verdi, ama ikisi çöktü:

```
cpp-baslik      6/12 → 12/12 → 12/12      (1. koşuda 35 satırın yalnız 8'i)
clojure-rapor   9/9  →  2/9  →  9/9       (2. koşuda 31 satırın yalnız 4'ü)
```

Çöküş, cevabın kısalmasıyla geliyor: model az sayıda satır seçiyor ve seçtikleri
doğru oluyor, ama gerisini hiç söylemiyor. `cpp-baslik`'in 1. koşusunda dosyanın
ilk yarısı seçilmiş, `class Olcer` ve serbest fonksiyonlar hiç görülmemiş.

**Bu, modelin küçüklüğüyle açıklanamıyor.** Üç koşunun en iyisi (115/116), köprünün
en küçük yedeğine — `nemotron-3.5-lightning-30b-a3b` — düştüğü koşu. En kötü
çöküş (`clojure` 2/9) ise yalnız `ultra`nın cevap verdiği koşuda oldu. Kısa cevap,
kapasite meselesi değil.

Bunun bir maliyeti yok: eksik satır uydurulmuş satır değil, ve
`sift peek <yol>` dosyanın tamamını bir komutta geri veriyor. Ama fazın dürüst
sınırı bu: **taslak, damıtmadan daha kararsız.**

### İkinci sınır: taslak bazen dosyanın kendisine dönüşüyor

42 taslağın 6'sında gösterilen satır sayısı dosyanın tamamına eşit çıktı —
`java-depo` üçünde birden, `sql-sema`, `hcl-altyapi` ve `clojure-rapor` birer
koşuda.

Yanlış hiçbir şey yok: gösterilen her satır dosyada var. Ama hiçbir şey de
elenmemiş. `haskell-ayristirici` bunun tipik örneği ve nedeni sözdiziminde:
Haskell'de bir fonksiyonun gövdesi de denklem biçimindedir, tip imzasıyla aynı
şekle sahiptir. Model ikisini ayırmakta zorlanınca 16 gövde satırının 16'sını da
gösteriyor.

Korpusun gösterilen kısmı %52-56. Faz 5'te damıtma %45-47'de kalıyordu. Yani
taslak daha az eliyor — ki soru düşünülürse beklenen bir şey: bir günlükte
gürültü çoğunluktadır, bir kaynak dosyasında bildirimler seyrek değildir.

### Kalıcı tek kaçık: iç içe bildirim

`python-akis` satır 27, üç koşuda da eksik:

```python
def sira(self) -> list[Adim]:
    ...
    def gez(ad: str) -> None:      # ← 27. satır
```

Bu, istemin kendi cümlesinin sonucu: *"dosya bundan fazlasını bildiriyorsa en
dıştaki bildirimleri tut, iç içe olanları dışarıda bırak."* Dosya 46 satır, yani
120'lik bütçenin çok altında — kural teknik olarak devrede değil. Model yine de
iç içe olanı elemiş.

Etiketi ölçümden sonra bağlama indirmedim. İndirseydim 348/348 çıkardı ve bu sayı
hiçbir şey ölçmezdi; cetveli sonuca uydurmak, cetveli kırmaktır.

## Geri dönüş yolu

Taslak, dosyanın küçük bir kısmını gösterir; geri kalanı sayar ve yolunu yazar:

```
─ 34 lines not shown · sift peek src/parser.rs for any of them ─
```

Bu satırın bir işe yaraması için `peek`'in dosya yollarını da alması gerekti.
`peek.bytes_of` önce depoya sorar, bulamazsa dosya sistemine bakar. Sıra
önemli ve mutasyonu var: çalışma dizininde bir yakalamanın adını taşıyan bir
dosya, o yakalamanın yerine cevap veremez.

Böylece iki komut da aynı çevrimi kapatıyor: **gördüğünü seç, seçmediğini say,
sayılana giden yolu yaz.**

## Mutasyonlar

Batarya 43'ten **49'a** çıktı, 49/49 yakalandı. Faz 6'nın altı yeni mutasyonu:

| değiştirilen | testin tutması gereken |
|---|---|
| `read_bytes().decode()` → `read_text()` | dosya baytla okunur, satır sonlarını kimse yeniden yazmaz |
| `select(read(path), …)` → yola dosya adını ekle | taslak dosyaya sorulur, adına değil |
| `judge.ask(question, …)` → `judge.ask(QUESTION, …)` | modele sorulan soru, çağıranın sorduğu sorudur |
| `peek` sırası: önce dosya, sonra depo | yakalamayı depo cevaplar, çalışma dizini ne tutarsa tutsun |
| `except OSError` → `except ValueError` | okunamayan dosya rapor edilir, kullanıcıya fırlatılmaz |
| `ends_of(path)` → `raise RuntimeError` | kimsenin seçmediği taslak hataya değil, dosyanın uçlarına düşer |

## Sırada

Faz 7 — MCP sunucusu. Şimdiye kadar yazılan her şey komut satırından
çalışıyor; sıra bunu bir istemcinin araç olarak çağırabileceği hâle getirmekte.
`distill` ve `outline` artık aynı motorun iki sorusu olduğu için, sunucunun
açacağı araç sayısı da ikiyle sınırlı kalabilir.
