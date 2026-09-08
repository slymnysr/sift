# 25 — Teklif: en çok kazandıran şeyin kendini tanıtması

**Nereden çıktı:** Kullanıcı isteği. "Şu hook olayı kullanıcıya sunulmalı, ne
verdiğini kısaca açıklayan bir bildiri ile; 'isterseniz kuralım' diyebilmeli."

## Sorun

18. faz, aracın en çok kazandıran parçasıydı: MCP yalnız istemcinin sift'e
**açıkça verdiğini** görür, oysa bir kodlama ajanı bunun dışında bir sürü kabuk
komutu çalıştırır ve hepsi konuşmaya bütün hâlde düşer.

Ve bu, aracın **açıkça açılması gereken tek parçasıydı.** Yazılı olduğu tek yer
README'ydi.

> Kimsenin bilmediği özellik, kimsede olmayan özelliktir.

## Ne yapıldı

```
sift hook --install [--yes]    ne verdiğini ve neye mal olduğunu söyler, sorar
sift hook --uninstall          geri alır
```

Ve `sift run`, kurulu değilse **bir kez, ömür boyu bir kez** bundan söz eder.
Söz ettiğini `$SIFT_HOME`'a işaretler ve bir daha söylemez. Tek seferin
alternatifi ya hiç söylememek (kimse bulamaz) ya da her seferinde söylemek — ki
o da bir mesajın okunmayı bırakma biçimidir.

## Teklifin dürüst olması

Yalnız kazancı sayan bir teklif, teklif değil satış konuşmasıdır. Bildiri iki
maliyeti de yazıyor ve biri gerçekten ısırabilir:

- **İstemcinin hook zaman aşımını aşan bir komut orada öldürülür ve istemci onu
  kendisi çalıştırır — yani çok uzun bir komut iki kez çalışabilir.** İki kez
  olmaması gereken şeyler için akılda tutulmalı.
- Yakalanan her komut bir model isteğine mal olur.

Bu ikisini yazmamak daha çok kurulum getirirdi. Testi de var (`run twice`
cümlesi aranıyor), çünkü "yazmıştım" bir süre sonra "silmiştim"e benziyor.

## Başkasının dosyasına yazmak

Asıl teknik iş bu. `~/.claude/settings.json` bu aracın sahibi olmadığı, insanın
çalışan yapılandırmasını tuttuğu bir dosya. Ölçülen gerçek: bu makinede zaten
`PreToolUse / Bash` altında `bash-guard.py` var.

Kurallar:

| Durum | Ne yapılıyor |
|---|---|
| Aynı matcher'da başka hook'lar var | **Yanına eklenir**, hiçbiri değişmez |
| Dosya yok | Oluşturulur |
| Zaten kurulu | Hiçbir şey yazılmaz |
| JSON değil, ya da tanınmayan şekil | **Reddedilir**, dosyaya dokunulmaz |
| İlk kurulum | Dosyanın kopyası `.before-sift` olarak bırakılır |
| Kaldırma | Yalnız bizimki gider; boş kalan matcher da gider (çöp bırakmamak için) |

Tanımadığı şekli **yeniden şekillendirmek yerine reddetmek** buradaki güvenliğin
tamamı: ne ile birleştiğinden emin olmayan bir birleştirme, birleştirmemeli.

## Onay

Terminal varsa sorar. Yoksa ve `--yes` da yoksa **reddeder** — kimsenin adına
karar vermez. Teklifi yine de basar, çünkü sormanın amacı okunmasıydı.

## Ölçü

- Önce: en çok kazandıran parça yalnız README'de yazılıydı ve elle JSON
  düzenlemeyi gerektiriyordu.
- Sonra: tek komut, dürüst bildiri, onay, yedek, geri alma; ve bir kereye mahsus
  hatırlatma.
- 17 test, 4 mutasyon.
