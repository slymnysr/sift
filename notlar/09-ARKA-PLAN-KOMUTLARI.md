# Faz 9 — Arka plan komutları

## Fazın cümlesi

Bitmeyen bir komut da damıtılabilir olmalı: başlat, prompt'unu geri al, **yalnız
son bakıştan beri geleni** oku, işin bitince durdur. Bunu yaparken tek bir söz
bozulmamalı — gösterilen satırın numarası, `sift peek` ile gidilecek satırın
numarasıdır.

## Neden bir gözcü süreç var

`sift run` komutu bekler, sonra görünümü verir. `--background` bekleyemez;
bütün amacı çağırana prompt'unu geri vermek. Ama komut bittiğinde orada birinin
olması gerekiyor, çünkü bir yakalamanın **sonradan yeniden kurulamayacak** tek
bilgisi budur: çıkış kodu. Çıkmış bir süreç, bir yabancıya nasıl bittiğini
anlatmaz.

Bu yüzden `sift.watch` var: başlatıcı onu başlatır, o komutu başlatır, bekler ve
`meta.json`'ı yazar. Model yok, ağ yok, yargı yok. Bir koşuyu dürüstçe
kapatabilen en küçük program.

İki şey buradan çıkıyor:

- **Baytlar gözcünün içinden geçmiyor.** Komut doğrudan yakalama dosyasına
  yazıyor. Gözcü öldürülse bile çıktı akmaya devam eder; kaybolan şey *son*'dur,
  ve `stop` tam bu yüzden gerektiğinde sonu kendisi yazar.
- **Durdurmak çalışıyor çünkü gözcü kendi oturumunun lideri.** Komut, kendi
  oturumu olmadan başlatıldığı için gözcünün grubuna düşer. Tek sinyal ikisini
  de — ve komutun doğurduğu dört derleyiciyi de — bitirir.

## Takip bir dilim, ayrı bir yakalama değil

En önemli tasarım kararı buydu ve alternatifi yazması daha kolaydı: her bakışı
kendi yakalaması olarak kopyalamak. Reddedildi, üç sebeple:

1. Diskteki baytı ikiye katlardı.
2. `sift list`'i tek bir koşunun parçalarıyla doldururdu.
3. `sift stats` bir komutu dört kez sayardı — projenin kendisi hakkında
   yayınladığı tek sayıyı şişirirdi.

Onun yerine `select` bir **`first` ofseti** aldı. 812. satır, `sift peek`'te de
812. satırdır. Ofset `read_numbers` → `render` → `narrow` → `select` zincirinin
tamamından geçiyor, çünkü buradan çıkan her numara sonunda `peek`'e gidiyor.

`render` içinde küçük ama önemli bir kural: **`first`'ten öncesi boşluk olarak
işaretlenmez.** Öncesi zaten bir önceki bakışta verilmişti; "900 satır
gösterilmedi" demek, okuyucuya zaten gördüğü şeyi kaçırdığını söylemek olurdu.

## İmleç dosyadır, değişken değil

Her `sift` çağrısı kendi sürecidir. Bellekte tutulan bir imleç her seferinde
sıfırdan başlar ve okuyucuya aynı bin satır tekrar verilir — ki bu aracın var
olma sebebi tam olarak o maliyetten kaçınmaktır. Bu yüzden `read.json`.

İmleç hem bayt hem satır tutuyor, çünkü ikisi farklı soruları cevaplıyor ve biri
diğerinden dosyayı yeniden okumadan çıkarılamıyor: bayt nereden okunacağını,
satır bir sonraki satırın numarasını söyler.

## Yarım satır beklet

Bir dilim, gelmiş **son satır sonunda** biter. Ondan sonrası, komutun hâlâ
yazmakta olduğu bir satırdır. Şimdi göstermek yarım satırı tam gibi sunar, öbür
yarısı da bir sonraki bakışta kendi başına bir satır gibi görünür: okuyucunun
görünümünde, çıktıda hiç var olmamış iki satır.

Bu kural aynı zamanda çözmeyi de garantiliyor: satır sonu baytı çok baytlı bir
karakterin parçası olamaz, dolayısıyla satır sonunda biten dilim tam sayıda
karakterle biter. Hiçbir harf iki bakış arasında ikiye bölünmez.

## Sessiz dakika bir cevaptır

Burası takibin bitmiş bir yakalamadan ayrıldığı tek yer. Bitmiş bir yakalamada
"hiçbir satır seçilmedi" bir arıza demektir — ne çalıştırıldığı ve nasıl bittiği
her zaman gösterilmeye değer — ve uçlar gösterilir. Ama yalnızca ilerleme çubuğu
basmış bir dakikada gerçekten okunmaya değer bir şey yoktur; bunu açıkça söylemek,
aracın uyanık olduğunu kanıtlamak için kırk satır göstermekten daha faydalıdır.

İkisi köprüye sorularak ayrılıyor: cevap verip hiçbir numara söylemeyen model
arkasında hata bırakmaz; hiç ulaşılamayan model bırakır.

Soru da farklı (`FOLLOWING`): ortadasın, sonuç yok, okuyucu öncesini zaten gördü.

## Durdurmak

Önce SIGTERM, çünkü toparlanabilecek bir komut o şansı hak eder — yazmanın
ortasında vurulan bir test koşucusu bozuk dosya bırakır. Sonra SIGKILL, çünkü
"kibarca rica edildi" bir koşuyu bitirme yöntemi değildir.

Sinyal sürece değil **gruba** gider. Ve tam bu yüzden bu fazın en tehlikeli
satırı burasıdır — aşağıya bakın.

## Bu fazın üç gerçek kusuru

**Bir: `stop()` yabancı bir süreç grubuna sinyal gönderebiliyordu.** `running.json`
bir dosyadır ve içindeki pid, işletim sisteminin geri verdiği bir numaradır. Sert
öldürülmüş bir gözcü dosyayı silemez; o numara okunduğunda başka birine ait
olabilir. `alive()` de bunu göremiyordu: `os.kill(pid, 0)` yabancı bir süreç için
`PermissionError` verir ve eski kod bunu "yaşıyor" sayıyordu. `pid=1` yazan bir
işaretçi `os.killpg(1, SIGTERM)` demekti.

Düzeltme `ours()`: pid ≤ 1 doğrudan reddedilir, ve pid'in hâlâ **grup lideri**
olması aranır. `launch` gözcüyü kendi oturumunda başlattığı için yaşadığı sürece
grup kimliği süreç kimliğine eşittir; numarayı sonradan devralan hiçbir şey bu
özelliği tesadüfen taşımaz.

**İki: zombi gözcü canlı sayılıyordu.** Çıkmış ama henüz toplanmamış bir süreç
pid'ini, grubunu ve sinyal 0'a verdiği cevabı korur — diğer her kontrole sağlıklı
bir süreç gibi görünür. Hiçbir şeyi izlemiyordur. Bu, komutu başlatıp yaşamaya
devam eden bir çağıran için gerçek bir durum (MCP sunucusu böyledir), ve tam da
"sert öldürülmüş gözcü" vakasını tespit etmesi gereken yerdir.

**Üç: tanıtıcı vardı, yakalama dosyası yoktu.** `launch` döndükten sonra gözcü
dosyayı açana kadar geçen anda `peek` de `follow` de "böyle bir yakalama yok"
diyordu. Artık dosya başlatma anında oluşturuluyor.

Not: birinci kusur, tamamen **yanlış bir hipotezi** kovalarken bulundu (oturum
çökmelerinin sebebi sanılmıştı; değildi — grup 1'in tek üyesi `init` ve SIGTERM'i
yakalamıyor). Hipotez yanlıştı, kusur gerçekti.

## Bu fazın dersi

**Bir grubu vuran araç, hedefin kendisine ait olduğunu önce kanıtlamalıdır.**

Bunun genel hâli şu: bir dosyaya yazılmış tanıtıcı — pid, tutamaç, oturum
numarası — okunduğu anda hâlâ doğru olduğunu ispatlamaz. Yazıldığı anda doğruydu.
Aradaki farkı ölçmeyen kod, eski bir numaraya güvenerek yabancı birine zarar
verir ve bunu "başarıyla durduruldu" diye raporlar.
