# 26 — Beklemek: cevap vermeyecek olanı beklemeyi bırakmak

**Nereden çıktı:** Kullanıcı "aynı işi sift'li ve sift'siz ölç" dedi. Ölçüm
kazancı değil, **gecikmeyi** ortaya çıkardı.

## Ölçülen felaket

| | komut | sift ilk kez | sift hatırlanmış | sift modelsiz |
|---|---:|---:|---:|---:|
| 404 satırlık derleme | 0,03s | **245,81s** | 0,18s | 0,09s |
| gerçek test paketi | 54,49s | **254,11s** | 56,30s | 55,61s |

Aynı iş bir başka koşuda **500,10 saniye** sürdü. Teorik tavan 540'tı
(3 basamak × 2 deneme × 90 sn), yani neredeyse ona vurmuştuk.

## Sebep: kuyruk, hesaplama değil

Amiral gemisi yavaş değil. **Sırası uzun.** Akışla ölçüldüğünde:

```
ultra-550b:  ilk token 120,29s → toplam 120,37s   (uretim 0,08s, 61 parca/s)
ultra-550b:  ilk token 120,00s → toplam 120,31s
super-120b:  toplam 3,65s
lightning:   toplam 18,06s
```

Üretim hızlı; beklemenin tamamı baştaki kabul kuyruğunda. Ve sayılar şüpheli
derecede yuvarlak — 120,00 ve 120,29 — yani değişken yoğunluk değil, **sabit bir
kapı** gibi duruyor.

`a55b` = token başına 55B aktif parametre, ~1TB+ GPU belleği. Ücretsiz katmanda
böyle bir kopyadan az vardır; `a12b` tek düğüme sığar, kopyası çoktur.

## 90 saniye seçilebilecek en kötü değerdi

```
kuyruk:  ████████████████████████ 107-124 sn
sift:    ██████████████████ 90 sn → kes
                            ↑ 17-34 saniye kala vazgeçiyor
```

Tam 90 saniye ödenip **hiçbir şey öğrenilmiyordu** — ne cevap, ne 503. Ve
`_TRIES_PER_RUNG = 2` bunu ikiye katlıyordu: aynı kuyruğa yeniden girmek.

Kullanıcının "bende opencode'da çalışıyordu" demesinin açıklaması da bu:
**o bekledi, sift beklemedi.**

## Kapı modelin, sağlayıcının değil

Aynı model iki bağımsız sağlayıcıda ölçüldü:

| nerede | ilk token |
|---|---:|
| NVIDIA doğrudan | boş döndü (99s, 88s) |
| OpenRouter | 92,14s / 88,01s |

Yani sağlayıcı değiştirmek amiral gemisini kurtarmıyor. Aynı koşuda
`super-120b:free` OpenRouter'da **1,24s**'de ilk token verdi.

## Yapılanlar

**1. Merdiven ölçüme göre.** Amiral gemisi çıkarıldı: `super` → `lightning`.
Sona konmadı, **çıkarıldı** — çünkü son basamak, üsttekilerin hepsi düştüğünde
gidilen yerdir, ve orası tam da kimsenin iki dakika bekleyemeyeceği andır.
`SIFT_MODELS` isteyene geri koyar.

**2. Zaman aşımı 90 → 25 sn.** Cevap verecek basamak ~6 saniyede veriyor;
kuyruktaki 100'ü aşıyor. 25, birincinin rahatça üstünde, ikincinin rahatça
altında.

**3. Zaman aşımında tekrar deneme yok.** 503 hızlı bir rettir, tekrarı ucuz;
zaman aşımı ise "kuyruk bizden uzun" demektir ve tekrarı **bir tam zaman aşımı
daha** ödetir. İkisi artık `Reply.timed_out` ile ayrılıyor.

Sonuç: en kötü durum **540 sn → 50 sn**.

## İkinci tur: hızlı ile sabırlı arasında seçim yapmamak

İlk tasarımda zaman aşımı tek bir sayıydı ve o yüzden bir ikilem doğuruyordu:
kısa tut, meşgul saatte vazgeç; uzun tut, her damıtmada iki dakika bekle.

Kullanıcının önerisiyle ikilem ortadan kalktı: **ikisi de olur, sırayla.**

```
1. TUR — çabuk (25 sn)     super → lightning
   ↓ hepsi zaman aşımına uğradıysa
2. TUR — sabırlı (150 sn)  super → lightning
```

Anahtar cümle: *"kimse 25 saniyede cevap vermedi", "kimse cevap vermeyecek"
demek değildir.* Ölçüm kuyruğun 107-124 saniyede açıldığını söylüyor; 150 onun
rahatça üstünde.

**Sabır yalnız kuyruğun ilacı.** Reddedilen anahtar (401) yürüyüşü bitirir —
beklemek yeni anahtar üretmez, sadece ölü bir anahtarı her basamağa iki kez
sunar. 404 de öyle: model yoksa beklemek onu var etmez. İkinci tur **yalnızca**
zaman aşımından sonra başlar.

**Ve olağan günde hiç ödenmez.** İlk tur cevap verince ikincisi hiç başlamıyor.
`SIFT_PATIENCE=0` çabuk bir "hayır"ı yavaş bir "evet"e tercih eden için.

Bir ayrıntı: iki turun ikisi de başarısız olursa dipnot **ikisini birden**
söylüyor (`no answer in 25s; then 150s: ...`). Yalnız ikincisini yazmak,
birincisi hiç olmamış gibi okunurdu.

## Efor: ölçüldü, alınmadı

Yol üstünde daha büyük bir şey bulundu. Model, 12 token'lık cevabı üretmek için
**924 token düşünüyor** ve çağıran bunun tamamını bekliyor.

Kontrollü ölçüm (aynı model, aynı 18 örnek, tek değişken efor):

| efor | gerekli satır | gürültü | süre |
|---|---:|---:|---:|
| **yok** | **115/115 — %100,0** | %53,2 | 130,0s |
| low | 106/115 — %92,2 | %28,6 | 39,3s |
| none | 102/115 — %88,7 | %21,1 | 37,9s |

3,3 kat hız, **%7,8 gerekli satır.** Ve kaybedilenler rastgele değil:

```
cobol-mainframe 32: $HASP395 FATURA ENDED - RC=0012     ← işin dönüş kodu
kubectl-hi 21,23,24,25,27: CrashLoopBackOff zinciri
gotest-zh 8: === RUN Test优惠券/折扣不得超过总价
```

Yani `low`, tam da bu aracın var olma sebebi olan yerlerde — çok dilli, alışılmadık
yapılı, gerçek arıza içeren çıktılarda — kaybediyor. **Varsayılan tam efor kalıyor.**
`SIFT_EFFORT` isteyene açık, ve bedeli README'de yazılı.

Bir uyarı: `reasoning_effort` her uç noktanın bildiği bir alan değil. Reddeden
bir uç nokta bir hız ayarını cevapsızlığa çevirmesin diye, 4xx alınca **aynı
basamağa alansız bir kez daha** soruluyor.

## Ölçümdeki iki hata, kayda geçsin

**Kesik üretimi tam sanmak.** İlk yoklamalarda `max_tokens=200` kullanıldı ve
"super 4 saniyede cevaplıyor" diye yazıldı. O rakam **kesilmiş** bir üretimin
süresiydi; gerçek süre ~10 saniye. Bir hız ölçümünde tavanı düşük tutmak, işin
bir kısmını ölçmemek demektir.

**Farklı kümeleri karşılaştırmak.** İlk efor kıyası "low, ultra ile aynı
kalitede" dedi (%97,6 vs %97,3). İki koşuda farklı sayıda örnek sessiz kalmıştı
— 20'ye 18, ve farklı örnekler. Kontrollü kümede gerçek fark %100'e %92,2 çıktı.
Faz 8'in notu bu tuzağı zaten yazmıştı; ikinci kez düşüldü.

Ders: **hız ölçümünde tavanı, kalite ölçümünde kümeyi sabitle.**
