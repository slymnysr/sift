# Faz 2 — Model köprüsü

`src/sift/model.py`: bir modele soru sorma, ya da soramadığını öğrenme yolu.
Damıtmanın kendisi Faz 3'te; burada yalnız köprü var.

## Basamaklı model

```
nvidia/nemotron-3-ultra-550b-a55b        amiral gemisi — her zaman ilk sorulan
nvidia/nemotron-3-super-120b-a12b
nvidia/nemotron-3.5-lightning-30b-a3b
```

Uç nokta `https://integrate.api.nvidia.com/v1`, OpenAI biçimli.
`SIFT_MODELS` ile merdiven tümüyle değiştirilebilir.

**Basamak inmek ulaşılabilirlikle ilgilidir, tasarrufla değil.** Her basamak
ücretsiz; en üstteki en iyi yargıyı veriyor. Aşağı inmenin tek sebebi üsttekine
ulaşılamaması. Bu, kullanıcının "en iyi modeli kullan, süre önemli değil"
talimatının koda yazılmış hâli.

**Canlı doğrulama (2026-08-31):** ultra 550B ilk denemede 6.6 saniyede cevapladı.
Süitte `test_the_bridge_really_reaches_nvidia` var ama `SIFT_LIVE=1` olmadan
kendini atlıyor: anahtar ve ağ isteyen bir test, wifi düştüğünde kırmızı yanar
ve insanlara süiti yok saymayı öğretir.

## Üç bilinçli karar

**Hiçbir şey fırlatılmıyor.** `ask` ya bir cevap döner ya hiçbir şey. Anahtar
yokluğu, ağ kopukluğu, meşgul model, anlamsız yanıt — bunların hiçbiri
kullanıcının sorunu değil ve hiçbiri komutunu çalıştırmakla görevli bir aracı
durduramaz. Ne olduğu `last_error`'a yazılıyor, bakmak isteyen bakar.

**İstemci kütüphanesi yok.** `urllib` ile tek bir POST. Başkalarının ortamına
kurulan bir araç, arkasında bir bağımlılık ağacı sürüklememeli; ortada
soyutlanacak bir şey de yok.

**Yalnız çağıranın verdiği şey makineden çıkıyor.** Kimlik yok, ortam yok, yol
yok, yan taraftan toplanan hiçbir şey yok. Gidenin ne olduğuna çağıran karar
verir; maskeleme Faz 9'un işi ve gizlice buraya alınmıyor. Bunu çiviyleyen test
`test_only_the_prompt_leaves_this_machine`, gövdedeki anahtar kümesini birebir
sabitliyor.

## Hata sınıflandırması

| Durum | Ne yapılıyor | Neden |
|---|---|---|
| 200, okunabilir | cevap döner | — |
| 200, okunamıyor / boş | **sonraki basamak** | aynı model aynı şekilde ifade eder; boş cevap, karar kılığına girmiş sessizliktir |
| 401 / 403 | **yürüyüş biter** | küçük model de aynı anahtarı aynı kararlılıkla reddeder; üstelik ölü anahtar bir yerine üç servise gösterilmiş olur |
| 0, 408, 409, 425, 429, 5xx | aynı basamakta bir kez daha, sonra aşağı | "şimdi değil" demek, "hiçbir zaman" demek değil |
| diğer 4xx (404 dahil) | **sonraki basamak**, aynı modele tekrar sorulmadan | istek hakkındaki bir olgu tekrarla düzelmez, ama başka model kabul edebilir |

Durum `0` "hiç ulaşılamadı" demek (ağ yok, DNS yok, bağlantı reddedildi) ve
meşgul durumlarıyla aynı kefeye konuyor — çünkü aynı şeyi söylüyor. Ağ
kesintisinin en iyi modele mal olmaması ayrıca test ediliyor.

## Anahtar

Sıra: `SIFT_API_KEY` → `NVIDIA_API_KEY` → `~/.config/nvidia/api_key`.
Dosya en sonda, çünkü bir kabuk tek bir komut için hiçbir şeyi düzenlemeden
üzerine yazabilsin. Anahtar yoksa `available` false döner ve `ask` ağa hiçbir
şey göndermeden hiçbir şey döner.

Testler `HOME`'u geçici dizine taşıyor: makinenin gerçek anahtarını sessizce
bulan bir test, kodu değil makineyi test eder.

## Mutasyon bataryası artık projenin parçası

`test/mutations.py` — `python test/mutations.py`.

Faz 1'de iki kez, geçen bir testin hiçbir şey kanıtlamadığı ortaya çıktı. Bu
yüzden batarya artık depoda duruyor ve her fazın kuralları buraya ekleniyor.
İki iyileştirme:

- **Önce temel yeşilliği doğruluyor.** Süit zaten kırmızıysa her mutasyon
  "yakalandı" görünür ve bütün alıştırma tiyatroya döner.
- **Çapa bulunamazsa kaçmış sayılıyor.** Sessizce atlanan bir mutasyon,
  korunmayan bir kuraldır.

Her mutasyon uygulanıp hemen geri alınıyor — koşum başarılı olsun, kırılsın ya
da yarıda kesilsin.

### Kaçan mutasyon: test kodu kendine karşı doğruluyordu

İlk koşumda 15'te 14 yakalandı. Kaçan kural: *en büyük model ilk sorulur.*
Mutasyon `DEFAULT_LADDER`'daki ultra ile super'in yerini değiştiriyordu ve
test hâlâ geçiyordu, çünkü test şunu diyordu:

```python
assert answer.model == m.DEFAULT_LADDER[0]
```

Yani koda "kendinle aynı fikirde misin?" diye soruyordu. Listeyi yeniden
sıralayın, beklenti de onunla birlikte sıralanır. Niyet yazılı değildi.

Artık amiral gemisinin kimliği test dosyasında **düz metin** olarak duruyor ve
ayrı bir test sıranın büyüklüğe göre olduğunu söylüyor: ultra → super →
lightning. NVIDIA modelleri yeniden adlandırırsa bu test kırılır — doğrusu da
budur, o zaman en üst basamağın hâlâ amiral gemisi olduğunu birinin
denetlemesi gerekir.

**Kural:** Bir test, beklentisini denetlediği koddan okuyorsa hiçbir şey
denetlemiyordur. Kural neyse testte kelimesi kelimesine yazılı olmalı.

Ayrıca bataryanın kendisinde bir kusur çıktı: `pyproject` zaten `-q` veriyor,
batarya bir `-q` daha ekleyince pytest `-qq` moduna geçip özet satırını hiç
basmıyordu. Temel satırı boş görünüyordu. Bir ölçüm aracının kendi çıktısını
okuyamaması, ölçtüğü şeye güvenmemek için yeterli sebep.

## Sırada

Faz 3 — damıtma çekirdeği: numaralanmış satırlar modele gider, model **yalnız
satır numarası** döner, metin yerel yakalamadan baytı baytına basılır. Uydurma
yapısal olarak imkânsız hâle gelir.
