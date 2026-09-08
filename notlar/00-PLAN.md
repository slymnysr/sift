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
3. **Fail-open.** Ağ yok, model 503, cevap saçma — hiçbiri aracı durdurmaz.
   Determinist yedek devreye girer. Bağlamı korumak için isteği düşüren bir
   araç, kazandırdığından çok kaybettirir.

   24. faz bunu bir yerde inceltti, esnetmeden: **kurulumu hiç bitmemiş makine**
   (anahtar yok, kapatma anahtarı da yok) ayrı bir durumdur ve MCP'de reddedilir.
   Sebep kuralın kendisi: terminaldeki insan zayıf görünümü görüp değerlendirir,
   ajan göremez. Reddetmek de bozmak değil — araç bir cümle döndürür, komutu
   çalıştırmadığını söyler, ajan kendi kabuğuyla devam eder. Komut satırında
   kural olduğu gibi durur: komut çalışır, çıkış kodu döner, uyarı bağırır.

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
| 19 | Kalıntı mutasyon | bataryanın bozduğu kural diskte kalmasın; yıkıcı işlemin önünde iki bağımsız koruma | bitti — [19-KALINTI-MUTASYON.md](19-KALINTI-MUTASYON.md) |
| 20 | Kayıt birimi | satırın birim olmadığı metinde kaydı birim yap | bitti — [20-KAYIT-BIRIMI.md](20-KAYIT-BIRIMI.md) |
| 21 | Saklama | yakalamalar sonsuza birikmesin; silinen kayıt sessiz kalmasın | bitti — [21-SAKLAMA.md](21-SAKLAMA.md) |
| 22 | Yanıt önbelleği | aynı girdiye aynı görünüm, ikinci kez sorulmadan | bitti — [22-YANIT-ONBELLEGI.md](22-YANIT-ONBELLEGI.md) |
| 23 | Ölçüm birimi | `stats` baytı değil, kurulan kişinin sorduğu şeyi saysın | bitti — [23-OLCUM-BIRIMI.md](23-OLCUM-BIRIMI.md) |
| 24 | Anahtar | kurulumu bitmemiş makine sessiz kalmasın; ajana daha kötü cevap verilmesin | bitti — [24-ANAHTAR.md](24-ANAHTAR.md) |

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

## 20-23 — bir rakip okunarak çıktı

18 faz kapandıktan sonra bağımsız bir proje bulundu: **Headroom**
(`headroomlabs-ai/headroom`), Rust ile yazılmış bir bağlam sıkıştırma katmanı;
kütüphane, vekil ve MCP sunucusu olarak çalışıyor. Aynı cümleyi kuruyor: araç
çıktısı bağlamı dolduruyor ve her turda yeniden gönderiliyor.

İskeleti de aynı: ham veri yerelde durur, geriye bir tutamak verilir, isteyince
aslı geri alınır (`headroom_retrieve` ↔ `sift peek`). Bağımsız iki proje aynı
şekle varmış.

Ayrıldıkları yer tek ve her şeyi belirliyor: **Headroom metni yeniden yazar,
sift satır seçer.** Bu yüzden Headroom doğruluk tablosu yayınlamak zorunda —
GSM8K 0.870 → 0.870, SQuAD %97 — çünkü kaybedebilir. Buranın böyle bir tablosu
olamaz, çünkü kaybedecek bir şeyi yok.

Karşılaştırmadan dört boşluk çıktı, ve dördü de "onlarda var" diye değil,
**burada ölçülebilir bir eksik** olduğu için faz oldu:

- **20** — Headroom'un JSON sıkıştırıcısı, buradaki asıl deliği gösterdi:
  seçim birimi satır. Tek satırlık 400 KB'lık bir dizide seçilecek bir şey yok.
  Alınan şey sıkıştırma değil, **birim fikri**.
- **21** — Headroom'un önbelleğinin bir TTL'i var. `store.py`'da hiçbir
  temizleme yoktu: `$SIFT_HOME` sonsuza büyüyordu.
- **22** — Headroom'un en büyük kazancı sıkıştırma değil, sağlayıcı
  önbelleğini bozmaması. Buradaki karşılığı: aynı dosyaya iki kez sorulmasın.
- **23** — Headroom dolar basıyor, ve ölçülemeyeni aralıkla veriyor. Buradaki
  `stats` bayt basıyordu; kurulan kişinin sorusu bayt değil.

**Alınmayanlar, gerekçesiyle:** düzyazı ve görsel sıkıştırma (1. kuralı bozar),
vekil (aşağıda, kendi gerekçesiyle), effort/verbosity yönlendirme (istek yolunda
oturmayı gerektirir, yani vekil), varsayılan açık telemetri (10. fazın tam
tersi), `learn` (16. faz bilerek modelsizdir).

**İstemci adaptörleri de alınmadı** ve bu bir kapsam kararıdır: `sift hook` bir
istemcinin olay biçimini biliyor. Başkaları için adaptör yazmak, doğrulanamayan
bir liste bakmak demek — 5. fazda dil listesinden kurtulmanın sebebi neyse, o.
`sift hook` stdin'den JSON okur ve stdout'a JSON yazar; bir istemci bu şekli
konuşuyorsa zaten çalışır, konuşmuyorsa aradaki çeviriyi yazmak onu kullananın
işidir ve burada tahmin edilemez.

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
