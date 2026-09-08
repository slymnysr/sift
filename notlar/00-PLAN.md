# sift — plan

## Bu proje ne

Bir komutun çıktısı çoğu zaman pahalı bir modelin bağlam penceresini doldurur ve
orada kalır: her turda yeniden gönderilir. `sift` komutu **kendisi çalıştırır**,
ham baytları diske yazar, ve pahalı modele yalnız **önemli olanı** verir.

Neyin önemli olduğuna karar veren şey **ücretsiz bir model**dir. Pahalı olanı
korumak için ucuz olanı çalıştırmak — projenin tek cümlelik ekonomisi budur.

## Neden baştan yazılıyor

Önceki tasarım (`winnow`) kararı **kurallara** vermişti: dil başına regex
"şekilleri", satır puanlama, desen listeleri. O tasarım 84 dil ailesi ve 260
uzantı biriktirdi ve hâlâ eksikti — çünkü her yeni dil elle eklenmek zorundaydı.

Bir model bunların hiçbirine ihtiyaç duymaz. Türkçeyi de, Japoncayı da, COBOL'u
da, daha dün çıkmış bir dili de zaten okur. Dil kapsamı bir **liste** olmaktan
çıkıp modelin doğal yeteneği haline gelir. Kullanıcının isteği bu yüzden haklı:
elimizde ücretsiz ve güçlü bir model varken kararı regex'e vermek israftı.

## Değişmeyen üç kural

Bunlar tasarımın omurgası. Hiçbir faz bunları esnetmez.

1. **Halüsinasyon yapısal olarak imkânsız.** Modelden asla metin istenmez;
   yalnız **satır numarası** istenir. Gösterilen metin her zaman yerel dosyadan,
   harfi harfine basılır. Model uydurabilir ama uydurduğu çıktıya giremez.
2. **Hiçbir şey silinmez.** Ham yakalama diskte durur; `peek` onu byte-for-byte
   geri verir. Görünüm bir **özet** değil, bir **seçim**dir; atlanan yer
   "burada 240 satır vardı" diye işaretlenir.
3. **Fail-open.** Anahtar yok, ağ yok, model 503, cevap saçma — hiçbiri aracı
   durdurmaz. Determinist yedek devreye girer. Bağlamı korumak için isteği
   düşüren bir araç, kazandırdığından çok kaybettirir.

## Fazlar

Her faz kendi başına çalışır durumda biter ve kendi testleri yeşil olmadan
sonraki faza geçilmez.

| # | Faz | Ne biter | Durum |
|---|-----|----------|---|
| 0 | İskelet | paket, `notlar/`+`test/`, pyproject, CI, ilk yeşil test | bitti |
| 1 | Yakalama | komutu kendi çalıştır, ham baytları sakla, byte-exact `peek` | bitti — [01-YAKALAMA.md](01-YAKALAMA.md) |
| 2 | Model köprüsü | NVIDIA NIM istemcisi, **basamaklı** model (ultra→super→lightning), zaman aşımı, yeniden deneme | bitti — [02-MODEL-KOPRUSU.md](02-MODEL-KOPRUSU.md) |
| 3 | Damıtma çekirdeği | numaralanmış satır → model → **yalnız numara** → yerel metin | bitti — [03-DAMITMA.md](03-DAMITMA.md) |
| 4 | Güvenlik ağı | model yokken determinist yedek; fail-open her yolda kanıtlanır | bitti — [04-GUVENLIK-AGI.md](04-GUVENLIK-AGI.md) |
| 5 | Dil bağımsızlığı | dünya dilleri + yazılım dilleri korpusu, ölçüm | bitti — [05-DIL-BAGIMSIZLIGI.md](05-DIL-BAGIMSIZLIGI.md) |
| 6 | Dosya taslağı | herhangi dilde bildirim çıkarımı (regex ailesi YOK) | bitti — [06-DOSYA-TASLAGI.md](06-DOSYA-TASLAGI.md) |
| 7 | MCP sunucusu | araçlar, kayıt, istemciye bağlanma | bitti — [07-MCP-SUNUCUSU.md](07-MCP-SUNUCUSU.md) |
| 8 | Bütçe ve ölçüm | pencereler arası bütçe, kazanç raporu, korpus kıyası | bitti — [08-BUTCE-VE-OLCUM.md](08-BUTCE-VE-OLCUM.md) |
| 9 | Arka plan komutları | bitmeyen komutlar: başlat, yalnız yeniyi oku, durdur | bitti — [09-ARKA-PLAN-KOMUTLARI.md](09-ARKA-PLAN-KOMUTLARI.md) |
| 10 | Gizlilik | sır maskeleme, opt-out, ham veri yerelde | bitti — [10-GIZLILIK.md](10-GIZLILIK.md) |
| 11 | Yayın | README, lisans, CI, PyPI | bitti — [11-YAYIN.md](11-YAYIN.md) |
| 12 | Çağıranın söz hakkı | `budget`, `keep` (mutlaka göster), `cwd` | bitti — [12-CAGIRANIN-SOZ-HAKKI.md](12-CAGIRANIN-SOZ-HAKKI.md) |
| 13 | Dosya damıtma | `digest`: var olan büyük bir dosyayı damıt | bitti — [13-DOSYA-DAMITMA.md](13-DOSYA-DAMITMA.md) |
| 14 | Arayan `peek` | desenle ara, eşleşme etrafında bağlam | bitti — [14-ARAYAN-PEEK.md](14-ARAYAN-PEEK.md) |
| 15 | Çoklu iş | bekleyen `follow`, tek çağrıda çok hedef, hepsini birden izle | bitti — [15-COKLU-IS.md](15-COKLU-IS.md) |
| 16 | Hafıza | bu dizinde ne çalıştı, nasıl gitti, hangi hata tekrar ediyor | bitti — [16-HAFIZA.md](16-HAFIZA.md) |
| 17 | Yoğun araçlar | `sg` / `diff` / `loc` çalıştır, çıktısını damıt | bitti — [17-YOGUN-ARACLAR.md](17-YOGUN-ARACLAR.md) |
| 18 | Kapsam | hook: istemcinin kendi kabuk çağrıları buraya gelsin | bitti — [18-KAPSAM.md](18-KAPSAM.md) |

## Ek fazlar — neden sonradan çıktılar

11 faz kapandıktan sonra eski proje (winnow) ile **özellik bazında** karşılaştırma
yapıldı ve sift'in kullanıcıya daha az yardım ettiği ortaya çıktı. Sebep mimari
bir tercih değildi: planı yazarken eski projenin araç listesi karşıya alınıp tek
tek işaretlenmedi. Hedef "var olan özellikleri **tümüyle** güncelle" diyordu;
ölçüt olarak envanter değil, tasarım ilkesi kullanıldı.

Bu bölümdeki yedi faz o boşluğun kapatılmasıdır. Ders, `notlar/12-*.md` içinde:
**bir yeniden yazımın ölçütü ilke değil envanterdir.**

Eklenmeyecek olan da kayda geçiyor: **vekil (proxy).** winnow'daki `proxy.py`
tüm konuşmayı API'ye giderken damıtıyor. Bu, komutun çıktığı yerde durmakla aynı
şey değil — ayrı bir üründür, ayrı bir güven modeli ister ve sift'in "yalnız
kendi çalıştırdığını görür" duruşunu bozar. Kapsam genişletmesi 18. fazda
**hook** ile yapılıyor: istemcinin kendi kabuk çağrısı buraya yönlendirilir,
komutu yine sift çalıştırır, ve hiçbir şey araya girmez.

### Fazların ortak kuralı

Yedisi de aynı çıtaya tabi: **yargı modelde, garanti kodda.** Yeni bir özellik
kodda "şu satır önemlidir" diyen bir kural getiriyorsa yanlış tasarlanmıştır.
`keep` bunun sınır örneği ve tam da bu yüzden 12. fazda: desen **çağırandan**
gelir, araç onu icat etmez — biri istektir, diğeri sezgisel tahmin.

## Kapsam kararları

- **Model:** varsayılan basamak `ultra` (550B) → `super` (120B) → `lightning`
  (30B). Ücretsiz katmanda amiral gemisi zaman zaman 503 verir; ölçülen bir
  gerçek, tasarımda karşılığı var.
- **Süre:** kullanıcı için önemli değil. Kalite hız uğruna feda edilmez.
- **Global:** arayüz metinleri İngilizce (dünya kullanacak), `notlar/` Türkçe
  (bakım dili). Kod ve testler İngilizce isimlendirilir.
- **Düzen:** testler yalnız `test/`, notlar yalnız `notlar/`. Kök dizin
  paylaşılabilir kalır — sonradan ayıklama işi olmayacak.
