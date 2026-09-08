# Faz 10 — Gizlilik

## Fazın cümlesi

Bu araç bir komutun çıktısını okuyor; o çıktı bazen bir anahtar, bir parola, bir
bağlantı dizesi içerir. Fazın işi tek bir soruyu net cevaplamak: **makineden ne
çıkar?** Cevap: yalnızca bir sorunun metni, maskelenmiş hâliyle — ve isteyen
kapatabilir.

## Tek kapı

Yakalama metnini makineden çıkacak bir şeye çeviren tek fonksiyon var: `rows()`.
Üç çağrı yeri de `distill.py` içinde. Maskeleme oraya konuldu, başka hiçbir yere
değil.

Bunun sonucu, bu mimarinin bedava verdiği bir özellik: **maskelenen satır
okuyucuya yine tam hâliyle gösterilir.** Çünkü modele yalnızca numara soruluyor
ve satırlar yerel dosyadan byte byte basılıyor. Maskeleme modele biraz bağlam
kaybettirir, okuyucuya hiçbir şey kaybettirmez. Varsayılan olarak açık olmasının
sebebi bu.

## Neden desen burada serbest

`fallback` desenleri en sert dille reddediyor. Aradaki fark yargıdır:

- Orada bir desen **yargılardı** — hangi satırın önemli olduğuna, yarım bildiği
  dillerde, kendinden emin biçimde yanlış karar verirdi.
- Burada hiçbir şey yargılanmıyor. Yanlış ateşleyen bir desen, bir prompt'ta bir
  maskelenmiş jetona mal olur. Ateşlemeyen bir desen bir anahtar sızdırır.

İki hata kıyaslanabilir değil. Kural: **şüphedeysen maskele.**

## Uzun ≠ yoğun ≠ sır

İlk yazdığım satır-boyu base64 kuralı fazla açgözlüydü ve mevcut bir testi kırdı:
`test_a_line_too_wide_to_judge_is_shortened_for_the_model_only` içinde satır
`"x" * 5000`. Beş bin tane `x` uzundur ama base64 değildir; kural onu tamamen
gizledi.

Kural daraltıldı: satırın tamamı base64 alfabesinden olacak **ve** karışık kasa
ile en az bir rakam içerecek. Genel hâli: bir commit özeti, bir sağlama toplamı,
bir log içindeki base64 yükü uzundur, yoğundur ve zararsızdır. Hepsini gizleyen
bir araç modele bir sayfa `[redacted]` verip buna gizlilik der.

Bunun kabul edilen bedeli: **hiçbir şeye benzemeyen çıplak bir sır geçer.**
Bu bir sınır ve üstü örtülmüyor — maskeleme kazara sızanı azaltır, hiçbir şeyin
çıkmayacağını garanti eden şey `SIFT_NO_MODEL`'dir.

## İki anahtar, iki kutup

| anahtar | ne yapar | varsayılan | tanınmayan değer |
|---|---|---|---|
| `SIFT_NO_MODEL` | gönderimi tamamen kapatır | kapalı (gönderim açık) | **kapatır** |
| `SIFT_MASK=0` | maskelemeyi kapatır | maskeleme açık | **açık bırakır** |

Kutuplar bilerek farklı. Gizlilik anahtarı yalnızca tam doğru yazıldığında
çalışıyorsa, o anahtar açığa düşerek başarısız olur. İkisinin varsayılanı da aynı
yöne bakıyor: makineden daha az şey çıksın.

`SIFT_NO_MODEL` açıkken üçüncü kural yine geçerli: çıktı ekrana gelir, çıkış kodu
komutun kendisidir, alt bilgi "switched off" der. Anahtarsızlığın, ağsızlığın ve
damıtıcıdaki bir hatanın kanıtlanmış olduğu şey, artık **kullanıcının kararı**
için de kanıtlı.

## Sıra: önce maskele, sonra kırp

Uzun satırlar modele gönderilmeden kısaltılıyor. Önce kırpılırsa, sınırı aşan bir
kimlik bilgisi yarım boyda gelir; hiçbir desen onu tanıyamaz ve kalan yarısı yine
bir sızıntıdır. Önce maskelenirse kırpılacak bir şey kalmaz. Bataryada kendi
kuralı var.

## `sift list` MCP aracı olmuyor

Faz 7'de ertelenen karar buydu ve karar veriliyor: **hayır.**

`follow` dört yüzüncü araç oldu çünkü tek bir tutamaç hakkında cevap veriyor ve o
tutamaca sahip olmanın tek yolu o koşuyu `run` ile başlatmış olmak — çağıranın
zaten sahip olduğu bir şey hakkında bir söz ekliyor.

`list` ve `stats` öyle değil. Makinede son zamanlarda çalışmış **her** komutu
devrederdi: başka projelerden, başka oturumlardan, modelin hiç sormadıklarını.
Terminaldeki insan o erişime zaten sahip; MCP üzerinden bağlanan bir model değil.
İkisi komut satırında kalıyor.

## Ham veri yerelde

Zaten böyleydi ve bu fazda kanıtlandı: baytlar yalnızca `$SIFT_HOME` altına
yazılır, ağa giden tek şey sorunun metnidir.

## Üretilmiş dosyanın sessiz kusuru

`privacy.py` ilk seferinde bir üreteç betiğiyle yazıldı ve desenler bozuk çıktı:
üreteç içindeki `"\\b"` kaçışları Python tarafından yorumlanıp gerçek **backspace**
karakterine (`\\x08`) dönüştü. Kelime sınırları yok oldu.

`ruff` temiz geçti. Geçmesi de gerekirdi: sözdizimi geçerliydi, `re.compile` hata
vermedi, dosya sorunsuz içe aktarıldı. **Çalışmayan bir desen de geçerli bir
desendir.** Kusuru bulan tek şey, on iki örnek satırı gerçekten maskeden geçiren
üç satırlık bir davranış kontrolüydü.

## Bu fazın dersi

**Bir kuralı yazmak, o kuralın ateşlendiğini kanıtlamaz.**

Bu fazda iki kez aynı biçimde ısırdı: bir kez desen hiç ateşlemedi (bozuk kaçış),
bir kez fazla ateşledi (beş bin `x`). İkisi de derleyiciden, linter'dan ve içe
aktarmadan geçti. Aradaki farkı yalnızca gerçek girdiyi verip çıktıya bakmak
gösterdi.
