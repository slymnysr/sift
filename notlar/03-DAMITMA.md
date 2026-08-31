# Faz 3 — Damıtma çekirdeği

`src/sift/distill.py`: projenin üzerinde durduğu fikir.

Yakalama numaralanır, modele **tek bir soru** sorulur — *hangi numaralar
önemli?* — ve model numara döner. Başka ne yazdıysa okunmadan atılır. Görünüm
sonra diskteki dosyadan basılır, satır satır, baytı baytına.

## Neden bu bir özetleyici değil

Bir özetleyici çıktınız hakkında cümle yazar ve o cümle çıktınızın söylemediği
bir şeyi söyleyebilir. Burada hiçbir şey satır yazmıyor.

Yanılmak hâlâ mümkün: yanlış satırlar seçilebilir. Ama o hatanın bedeli
**görünümden eksik bir satır**, asla komutun söylemediği bir satır değil. Ve
eksik satır bir `sift peek` uzaklıkta, çünkü dosyaya hiç dokunulmadı.

Aynı sebeple **kapsam bir liste değil.** Bu dosyada Rust yığın izinin neye
benzediğini, Japonca hata mesajının ne dediğini, daha dün çıkmış bir dilin
başarısızlığı nasıl bildirdiğini bilen hiçbir şey yok. Model bunları zaten
biliyor. Eksik kalabilecek bir tablo ortada yok — `winnow`'da 84 dil ailesi ve
260 uzantı vardı ve hâlâ eksikti.

## Akış

```
capture.text()  →  numbered()  →  Bridge.ask()  →  read_numbers()  →  render()
   ham baytlar     "12| ..."      yalnız numara     numara kümesi     yerel metin
```

`read_numbers` modelin cevabından **yalnız sayıları** alır. Etrafındaki düzyazı
reddedilmez, görmezden gelinir: kendini açıklayan bir model soruyu yine de
cevaplamıştır ve güvenilmeyecek kısım zaten açıklamadır.

Yakalamada olmayan numaralar **düşürülür**. Var olmayan bir satır gösterilemez;
uydurmak da bu tasarımın engellemek için var olduğu şeyin ta kendisi.

## Üç sessiz tuzak, üçü de test edilmiş

**Aralık uçları kırpılıyor ama sayılmıyor.** `1-9999` üç satırlık bir yakalamada
1-3'e kırpılır. Kırpma yapılmazsa görünüm yine doğru görünür — çünkü
`lines[9998:9999]` boştur — ama `kept` 9999 der ve boşluk işaretleri o yalanın
üzerine hesaplanır. Bu yüzden testler `_shown` uzunluğunun yanında `kept` ve
gizlenen satır toplamını da doğruluyor. Görünüşte doğru bir çıktı, bozuk bir
sayaç saklayabilir.

**Parçalı sorularda numaralandırma kayabilir.** Uzun bir yakalama pencerelere
bölünür; her pencere **yakalamanın kendi numarasıyla** başlar. Her parçayı 1'den
numaralasak, ilkinden sonraki her cevap dosyanın başını gösterirdi — kendinden
emin ve yanlış.

**İstemin kısaltması görünüme sızabilir.** Binlerce karakter genişliğindeki bir
satır modele ilk 400 karakteriyle gösterilir (yargı için başı yeter). Gösterilen
metin **asla** kısaltılmaz; o dosyadan gelir. İkisi ayrı yollar ve ayrı test
ediliyor.

## Boşluk işareti

```
─ 3,914 lines not shown · sift peek a3f1 for any of them ─
```

Kaç satır olduğunu ve nasıl okunacağını söyler. Sessizce saklayan bir görünüm
kendisine güvenilmesini isterdi; bu görünüm denetlenebilir. Bir test işaretlerin
toplamının `total - kept`'e eşit olduğunu doğruluyor: sayılar dürüst olmak
zorunda.

## Yargı yoksa görünüm de yok

Anahtar yok, modele ulaşılamadı ya da cevapta hiç sayı yok → `distill` **hiçbir
şey döner**. Tahmin etmek burada yedeğin eksik olduğunu gizlerdi. Yedek Faz 4'ün
işi ve gizlice buraya alınmıyor.

## Mutasyon bataryası

25 kural (Faz 1'den 6, Faz 2'den 9, Faz 3'ten 10). Faz 3 kuralları yazılırken iki
test kendi başına yetersiz çıktı ve mutasyonlar yazılmadan **önce**
sıkılaştırıldı: kırpma sayaç üzerinden, kuyruk boşluğu ise erken biten bir seçim
üzerinden denetleniyor.

Bataryaya süzgeç eklendi: `python test/mutations.py numbering` yalnız kuralı
eşleşen mutasyonları koşar. Kaçak bulmakla düzeltmek arasındaki dakikalar için;
süzülmüş koşum geçmiş sayılmaz ve sonunda bunu kendisi söylüyor.

### Kaçan mutasyon: ilk ve son doğruyken ortadakiler yanlış olabilir

İlk koşumda 24'te 23 yakalandı. Kaçan kural: *sonraki parça bütünün
numarasıyla numaralanır.* Mutasyon `_windows` döngüsündeki `start + 1`'i `1`
yapıyordu ve test hâlâ geçiyordu.

Sebep: yakalama 8.000 satırdı, yani **iki** pencere çıkıyordu. İlk pencere zaten
1'den başlıyor (mutasyon orada görünmez), ikinci pencere ise döngüden değil
döngü sonrasındaki son `append`'ten geliyor — mutasyon oraya hiç dokunmuyordu.
Mutasyonun bozduğu tek şey **ortadaki** pencerelerdi ve testte ortadaki pencere
diye bir şey yoktu.

Test artık 20.000 satır kullanıyor (en az üç parça, yani gerçek bir orta) ve
ikinci parçanın ilk satırını değil, **her parçanın her numaralı satırını**
yakalamanın kendisiyle karşılaştırıyor. Son `append` için de ayrı bir mutasyon
eklendi.

**Kural:** Bir sınır davranışını test ediyorsanız, sınırların *arasında* bir şey
bıraktığınızdan emin olun. İki elemanlı bir örnek uçları test eder, ortayı değil.

## Açık kalem: `sift.cli` yok

`pyproject.toml` `sift = "sift.cli:main"` ilan ediyor ama `cli.py` henüz
yazılmadı — `uv run sift` şu an `ModuleNotFoundError` veriyor. Faz 4'te
kapanıyor, çünkü komut satırı arayüzünün ilk sözü fail-open: model olmadan da
bir şey göstermek. O fazda ilan edilen giriş noktasının gerçekten çözüldüğünü
denetleyen bir test de ekleniyor.

## Sırada

Faz 4 — güvenlik ağı: model yokken determinist yedek, `sift.cli`, ve fail-open'ın
her yolda kanıtlanması.
