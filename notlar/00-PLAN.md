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
| 7 | MCP sunucusu | araçlar, kayıt, istemciye bağlanma |
| 8 | Bütçe ve ölçüm | kazanç raporu, korpus kıyası |
| 9 | Gizlilik | sır maskeleme, opt-out, ham veri yerelde |
| 10 | Yayın | README, lisans, CI, PyPI |

## Kapsam kararları

- **Model:** varsayılan basamak `ultra` (550B) → `super` (120B) → `lightning`
  (30B). Ücretsiz katmanda amiral gemisi zaman zaman 503 verir; ölçülen bir
  gerçek, tasarımda karşılığı var.
- **Süre:** kullanıcı için önemli değil. Kalite hız uğruna feda edilmez.
- **Global:** arayüz metinleri İngilizce (dünya kullanacak), `notlar/` Türkçe
  (bakım dili). Kod ve testler İngilizce isimlendirilir.
- **Düzen:** testler yalnız `test/`, notlar yalnız `notlar/`. Kök dizin
  paylaşılabilir kalır — sonradan ayıklama işi olmayacak.
