# Faz 5 — Dil bağımsızlığı

`src/sift/lines.py`, `test/korpus/`, `test/korpus_reader.py`, `test/languages.py`.

Projenin en büyük iddiası bu fazda ilk kez **sayıyla** sınanıyor: `sift` hiçbir
dil listesi tutmuyor, çünkü karar veren model dilleri zaten biliyor. Bu cümle
plandan beri yazılı duruyordu ama hiçbir yerde ölçülmemişti. Ölçülmeyen iddia
iddia değildir; reklamdır.

İki iş yapıldı. Önce **satırın tek bir tanımı** yazıldı — çünkü ölçmeden önce
neyi saydığımızın her dilde aynı şey olduğundan emin olmak gerekiyor. Sonra 19
insan dili ve 22 araç zincirinden oluşan **etiketli bir korpus** kuruldu ve
seçim bu korpusta ölçüldü.

## Bir satır nedir

Python'un `str.splitlines()` metodu, hiçbir terminalin, hiçbir editörün ve
`wc`'nin satır sonu saymadığı sekiz karakterde daha satır böler:

```
U+000B  düşey sekme        U+001E  kayıt ayırıcı
U+000C  sayfa atlatma      U+0085  NEL (sonraki satır)
U+001C  dosya ayırıcı      U+2028  LINE SEPARATOR
U+001D  grup ayırıcı       U+2029  PARAGRAPH SEPARATOR
```

Bunlar teorik değil. **NEL**, EBCDIC'ten dönüştürülmüş anabilgisayar
günlüklerinden çıkar — korpustaki `cobol-mainframe` örneğinde gerçek bir tane
var. **Sayfa atlatma**, eski yazılımların çıktısını sayfalara bölme alışkanlığından
kalmadır. **U+2028**, JavaScript kaynaklarından ve bazı JSON serileştiricilerden
gelir.

Sonuç şu olurdu: bir yakalama, dünyada başka hiçbir aracın var olduğunu kabul
etmediği satırlar kazanır. `sift peek 40 50` ekranın yanındaki editörden
**başka bir metinle** cevap verir. Numaralar kayar ve kaydıklarını kimse
söylemez.

Ayrıca kendini yeniden çizen bir ilerleme çubuğu **tek satırdır**. Satır
ortasındaki `\r` korunur; yalnız `\n`'in hemen önündeki `\r` satır sonuna
aittir. 900 kez yeniden çizilen bir çubuk, komutun söylediği her şeyi oy
çokluğuyla bastırmamalı.

```python
def of(text: str) -> list[str]:
    """The lines of `text`, counted the way the rest of the world counts them."""
    if not text:
        return []
    found = text.split("\n")
    if found[-1] == "":
        # A trailing newline ends the last line; it does not begin another one.
        found.pop()
    return [line[:-1] if line.endswith("\r") else line for line in found]
```

Üç çağrı yeri bu tanıma bağlandı: `distill.py` (modele numaralanmış görünümü
veren yer), `fallback.py` (baş/son kesen yer) ve `peek.py` (numaraya karşılık
metni döndüren yer). Üçü aynı sayıyı saymazsa numaralar birbirini tutmaz.

Test bunu **bağımsız bir hakemle** doğruluyor: `wc -l`. Beklentiyi denetlediği
koddan okuyan bir test hiçbir şey kanıtlamaz. `test/test_lines.py` ayrıca
`text.splitlines() != lines.of(text)` olduğunu da doğruluyor — böylece test
boş yere yeşil kalamaz.

## Baytla okumak — bu fazda çıkan bulgu

`ansi-progress` örneğinin satır sayısı doğrulama betiğimde 17 yerine 23 çıktı.
Sebep örnekte değildi, betikteydi: `Path.read_text()` **evrensel satır sonları**
davranışını açar ve her `\r`'yi `\n`'ye çevirir. Örnekteki 6 yeniden çizim, hiç
yazılmamış 6 satıra dönüşmüştü.

Üretim tarafı güvenliydi — `store.read_raw` baytla okuyor (`store.py:136`,
`return p.read_bytes()`) ve çözümlemeyi `Capture.text()` yapıyor. Ama bu bir
tesadüf değil, **kural** olmalıydı: boru ile görünüm arasında hiçbir katmanın
satır sonu hakkında fikri olamaz.

Bulgu üç yere sabitlendi:

- `test/korpus_reader.py` örnekleri baytla okur, belgesinde nedeni yazılıdır.
- `test_a_capture_keeps_the_carriage_returns_the_command_wrote` uçtan uca
  doğrular: gerçek bir komut `[1/3]\r[2/3]\r[3/3]\n` yazar, yakalamada `\r`'ler
  durur, `lines.of` tek satır sayar.
- `mutations.py`'ye bir mutasyon eklendi: `read_bytes()` → `read_text(...)`.
  Süit bunu yakalamazsa kural korumasızdır.

## Korpus

`test/korpus/` — aynı gövdeye sahip iki dosya: `<ad>.txt` çıktının baytları,
`<ad>.json` onun hakkında bilinenler. `src/` bu klasörün varlığından haberdar
değil; asıl mesele bu. Seçim bir dil listesine dayansaydı, kimsenin aklına
gelmeyen bir dilde örnek eklemek bir şeyi bozardı — ve eklemek bunu öğrenmenin
yoludur.

| örnek | araç | dil | yazı | koşum | satır | zorunlu | gürültü |
|---|---|---|---|---|---|---|---|
| ansi-progress | npm/webpack | en | latin | başarı | 17 | 3 | 14 |
| cargo-de | cargo | de | latin | hata | 43 | 9 | 20 |
| cmake-vi | cmake | vi | latin | başarı | 25 | 4 | 21 |
| cobol-mainframe | cobol/jcl | en | latin | hata | 32 | 8 | 23 |
| docker-ar | docker | ar | arabic | hata | 43 | 9 | 29 |
| dotnet-fr | dotnet | fr | latin | hata | 15 | 5 | 10 |
| ffmpeg-fa | ffmpeg | fa | arabic | hata | 36 | 5 | 31 |
| gcc-ru | make/gcc | ru | cyrillic | hata | 21 | 7 | 11 |
| git-quiet | git | en | latin | başarı | 9 | 2 | 0 |
| gotest-zh | go test | zh | cjk | hata | 23 | 9 | 14 |
| gradle-ko | gradle | ko | cjk | hata | 33 | 6 | 27 |
| journalctl-it | journalctl | it | latin | hata | 23 | 6 | 17 |
| kubectl-hi | kubectl | hi | devanagari | hata | 41 | 11 | 30 |
| latex-pl | pdflatex | pl | latin | hata | 38 | 4 | 26 |
| maven-tr | maven | tr | latin | hata | 36 | 8 | 27 |
| mix-he | mix test | he | hebrew | hata | 19 | 7 | 11 |
| psql-es | psql | es | latin | hata | 26 | 5 | 19 |
| pytest-en | pytest | en | latin | hata | 30 | 6 | 17 |
| rspec-id | rspec | id | latin | hata | 21 | 7 | 11 |
| terraform-pt | terraform | pt | latin | hata | 40 | 4 | 32 |
| vite-ja | npm/vite | ja | cjk | hata | 28 | 7 | 17 |
| zig-sw | zig build | sw | latin | hata | 22 | 8 | 10 |

**22 örnek · 621 satır · 19 insan dili · 6 yazı sistemi · 22 araç zinciri · 3
başarılı koşum.** Son rakam kasıtlı: yalnız bir şey bozukken çalışan araç
bitmiş sayılmaz. Sağdan sola üç dil (ar, fa, he), CJK üç dil (ja, zh, ko),
Devanagari, Kiril ve bir anabilgisayar günlüğü var — sonuncusu gerçek U+000C ve
U+0085 içeriyor, yani yukarıdaki satır tanımını fiilen sınıyor.

Korpusun kendisi de test ediliyor (`test/test_korpus.py`, ~139 parametreli
test): her etiketin bir örneği ve her örneğin etiketi var mı, etiketteki satır
sayısı kodun gördüğü sayıyla aynı mı, işaretli satırlar gerçekten var ve dolu
mu, bir satır hem zorunlu hem gürültü olarak işaretlenmiş mi, korpus kanıt
sayılacak kadar geniş mi (≥18 dil, ≥6 yazı, ≥20 araç, ≥3 başarı, ≥15 hata).

## Zorunlu satır ölçütü

> Bir satır, o satır olmadan kişi doğru sonuca varamıyorsa zorunludur.

Bu ölçüt bilerek dar. İnsanın içinden hata bloğunun tamamını işaretlemek
geliyor; ama bir alt çizginin, bir `|` çerçevesinin, çıplak bir `Failures:`
başlığının ya da `Enter file name:` isteminin gösterilmesini şart koşmak ölçümü
**sıkılaştırmaz, cetveli yanlışlaştırır.** Yanlış cetvel kimseyi övmez.

İlk ölçümden sonra bu ölçüte göre **15 etiket** bağlama indirildi (ne zorunlu ne
gürültü — puanda hiçbir tarafa yazılmaz):

| örnek | satır | neden |
|---|---|---|
| docker-ar | 38, 41 | hatanın komşuluğundaki değişmemiş Dockerfile satırları |
| gcc-ru | 15 | önerinin tekrarı; öneri 12. satırda tam yazılı |
| latex-pl | 28, 29, 31 | TeX'in etkileşimli istemi |
| latex-pl | 33 | `<read *>` çerçevesi |
| maven-tr | 25 | çıplak başlık |
| mix-he | 13 | çıplak başlık |
| psql-es | 26 | çıkış komutu |
| rspec-id | 19 | çıplak başlık |
| terraform-pt | 37 | 36. satırın gösterdiği kaynak satırının tekrarı |
| terraform-pt | 40 | yalnız istek kimliği |
| zig-sw | 20, 21 | ağaç çerçevesi; özet zaten 19. satırda |

Bunun sonuca göre etiket ayarlamak olmadığını açıkça yazmak gerekiyor: ölçüt
**tüm örneklere aynı anda** uygulandı — tam puan alanlar dâhil — ve **satırlara**
uygulandı, puanlara değil. Zorunlu satır sayısı 155'ten 140'a indi.

## Ölçüm

`test/languages.py` bir test değil, elle çalıştırılan bir betiktir. Anahtar
ister, ağ ister ve örnek başına bir gerçek istek harcar. `test/` altındaki her
şey çevrimdışıdır çünkü her şey sormadan karara bağlanabilir; bu bağlanamaz.

```
uv run python test/languages.py            # tüm örnekler
uv run python test/languages.py ja ko zh   # eşleşenler
uv run python test/languages.py arabic     # yazı sistemi ve araç da eşleşir
```

Örnek başına iki sayı: görünümün **onsuz yanlış olduğu** satırların kaçı geri
geldi (iddia budur, hepsi olmalı), ve gürültünün ne kadarı beraberinde geldi
(aracın çalışmaya değip değmediği budur, yalnız küçük olmalı).

Aynı korpus üç kez ölçüldü. Aradaki tek fark modelin o anki keyfi:

| koşu | zorunlu satır | gürültü | korpusun gösterileni | basamak |
|---|---|---|---|---|
| 1 | **139/140** | 132/417 (%32) | 295/621 (%47) | ultra |
| 2 | **140/140** | 117/417 (%28) | 287/621 (%46) | ultra + super |
| 3 | **138/140** | 109/417 (%26) | 280/621 (%45) | ultra + super |

Üç koşuda toplam 420 zorunlu satır fırsatının **417'si** geri geldi. Kaçan üç
satır şunlar:

```
latex-pl        32  ! Emergency stop.                              (koşu 1)
cobol-mainframe 13  14.02.19 JOB09412 -RUNSTEP GO ...              (koşu 3)
gcc-ru          19  cc1: все предупреждения считаются ошибками     (koşu 3)
```

Asıl sonuç bu üç satırın **nerede** olduğu. Fazın sorusu "seçim İngilizce
dışında zayıflıyor mu" idi; cevap ölçülebilir biçimde hayır:

| yazı sistemi | fırsat (3 koşu) | gelen |
|---|---|---|
| latin | 237 | 235 |
| arabic (ar, fa) | 42 | 42 |
| cjk (ja, zh, ko) | 66 | 66 |
| devanagari (hi) | 33 | 33 |
| hebrew (he) | 21 | 21 |
| cyrillic (ru) | 21 | 20 |

Latin dışı 183 fırsatın 182'si geldi (%99,5); Latin'de 237'nin 235'i (%99,2).
Yani sağdan sola yazılan Arapça ve İbranice, CJK, Devanagari ve Kiril, Latin
alfabesinden **daha kötü değil**. Elimizde hiçbir dil listesi yokken.

Kaçan üç satır da ilginç: üçü de aracın "sonuç" satırı değil, sonuca giden
satır. `! Emergency stop.` TeX'in durma nedeni, ama TeX aynı şeyi başka türlü
de söylüyor; JCL adım muhasebesi bir hata metni gibi görünmüyor; Rusça
`cc1: ...` satırı "tüm uyarılar hata sayılır" diyor ve derleyicinin asıl hata
satırlarının yanında ikincil duruyor. Model her üçünde de yanlış satır
seçmedi — **daha az** satır seçti.

Gürültü tarafı: gösterilen korpus üç koşuda %45–47 arasında, gürültünün
%26–32'si beraberinde geliyor. Yani ortalama olarak yakalamanın yarısından
biraz fazlası ekrana gelmiyor ve gelmeyenlerin neredeyse tamamı gürültü.

Örnek bazında oynama küçük değil: `docker-ar` üç koşuda 24, 17, 18 satır
gösterdi; `cmake-vi` 10, 6, 6. Ama bu oynamanın tamamı **gürültü tarafında**
kaldı — ikisi de her koşuda zorunlu satırlarının hepsini verdi. Model ne kadar
bağlam ekleyeceğinde kararsız, neyin önemli olduğunda değil.

Beş örnek (`zig-sw`, `vite-ja`, `gradle-ko`, `git-quiet`, `ffmpeg-fa`) üç koşuda
satırı satırına aynı görünümü üretti.

## Ölçüm neden testin içinde değil

Çünkü sonucu koşudan koşuya değişiyor ve **tek koşu alıntılanabilir bir sayı
değildir.** Bunu ölçerken öğrendik: `psql-es` bir koşuda 3/6, hemen ardından
5/6 verdi. Puanlayıcı doğruydu, model kararsızdı.

Bu sayıyı CI'ya koymak iki kötü seçenekten birine zorlar: ya eşik gevşek olur ve
hiçbir şey ölçmez, ya da sıkı olur ve derlemeler modelin o günkü keyfine göre
kırmızıya döner. İkisi de dekoratif altyapıdır. Bu yüzden eksik bir zorunlu
satır **hata değil, ölçümdür** — betik çıkış kodu 1 verir ve o dilde seçimin
İngilizceden zayıf olduğunu söyler.

## Mutasyonlar

Faz 5 dört yeni mutasyon getirdi ve toplam **43** oldu:

| dosya | kural |
|---|---|
| lines.py | satır yalnız `\n`'de biter, başka hiçbir şeyde bitmez |
| lines.py | sondaki satır sonu son satırı bitirir, yenisini başlatmaz |
| lines.py | `\n` öncesindeki `\r` satır sonuna aittir |
| store.py | yakalama baytla okunur, satır sonlarını hiçbir şey yeniden yazmaz |

Batarya bu fazda **43/43 yakalandı** ile kapandı. Yeni dördü de dahil: satır
tanımının her parçası ve baytla okuma kuralı, bozulduklarında süiti kırmızıya
çeviriyor. Yakalanmayan bir mutasyon küçük bir sorun olmazdı — o kuralın
korumasız olduğu, ve o satırı bir sonraki değiştirenin "her şey yolunda"
duyacağı anlamına gelirdi.

## Sırada

Faz 6 — dosya taslağı: çıktıdaki dosya/satır bildirimlerinin herhangi bir dilde
çıkarılması. **Regex ailesi yok**; bu fazın kuralı da aynı, karar modelin.
