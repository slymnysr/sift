# Faz 11 — Yayın

## Fazın cümlesi

On faz boyunca yazılan şeyin, bu makinenin dışında da var olabilmesi. Bunun üç
parçası var ve üçü de birer sözdür: **README** ne yaptığını söyler, **CI** her
işletim sisteminde çalıştığını gösterir, **yayın** onu kurulabilir yapar.

## Geri alınamayan tek işlem

PyPI'ye çıkmış bir sürüm geri alınamaz. Silinebilir, ama o numara bir daha
kullanılamaz ve birileri onu çoktan çekmiş olabilir.

Bu yüzden yayın **yalnızca bir etikete** bağlı:

```yaml
on:
  push:
    tags: ["v*"]
```

`main`'e yapılan bir itme hiçbir koşulda yayınlayamaz. "Birleştirildi" ile
"yayınlandı" arasındaki fark, kasıtlı bir jest olmalı — ve bu kuralın bataryada
kendi mutasyonu var: `tags` yerine `branches` yazıldığında testin bunu
yakalaması gerekiyor.

## Etiket ile sürüm aynı olmalı

İki ayrı yerde, iki ayrı zamanda, çoğu zaman ikisini de aynı anda hatırlamayan
biri tarafından yazılıyorlar: `pyproject.toml` içindeki `version` ve `git` etiketi.
Yayın işi ikisini karşılaştırıyor, güvenmiyor. Adı etiketiyle uyuşmayan bir
tekerlek, sonradan kimsenin hakkında akıl yürütemeyeceği bir sürümdür.

Aynı hizalama paket içinde de test ediliyor: `sift.__version__` ile
`pyproject.toml` ayrışırsa Faz 0'dan beri duran bir test kırmızıya döner.

## Saklanan bir jeton yok

Yayınlama **güvenilir yayınlama** (trusted publishing) ile yapılıyor: PyPI'ye
hangi deponun, hangi iş akışının bu projeyi yayınlayabileceği söyleniyor ve
GitHub bunu kanıtlayan kısa ömürlü bir jeton imzalıyor.

Hiçbir yerde saklanan bir API jetonu yok. Dolayısıyla sızacak, döndürülecek ya da
yanlışlıkla loglanacak bir sır da yok. Bu, Faz 10'un kararının altyapı tarafındaki
karşılığı: **çıkmayan şey sızmaz.**

## Sürüm: 1.0.0, ama "4 - Beta"

İkisi çelişkili görünüyor, bilerek öyle:

- **1.0.0**, yüzeyin oturduğunu söylüyor. Yedi komut, dört MCP aracı, üç kural.
  Bunlar on bir faz boyunca ölçülerek yerine oturdu ve kırılmadan değişmeleri
  beklenmiyor.
- **4 - Beta**, bu makinenin dışında henüz kimsenin çalıştırmadığını söylüyor.
  Saha deneyimi yok. Bunu "Production/Stable" diye yazmak, sahip olmadığım bir
  bilgiyi iddia etmek olurdu.

Sürüm numarası bir arayüz sözüdür, sınıflandırıcı bir olgunluk beyanıdır. İkisi
farklı şeyler söylüyor çünkü farklı şeyler biliniyor.

## README bir söz, o yüzden ölçülüyor

README bir aracın ön kapısı ve genellikle koddan aylar sonra okunur. Bu fazda üç
test eklendi:

| test | ne tutuyor |
|---|---|
| komutlar | `cli.USAGE`'daki her komut README'de geçiyor mu |
| araçlar | sunucunun sunduğu her araç README'de anılıyor mu, ve **anılmayan bir araç vaat edilmiyor mu** |
| yayın | `release.yml` gerçekten yalnız etikete mi bağlı |

İkinci sütun iki yönlü çünkü iki farklı hata var: README'de yazılmayan bir araç
kimsenin çağırmadığı bir araçtır; README'de yazılıp sunulmayan bir araç ise
kullanıcıya çalışmayacak bir şeyi tarif etmektir.

`list` ve `stats`'ın MCP'de **olmadığı** da README'de açıkça yazıyor ve testi var.
Bir eksikliğin kasıtlı olduğunu söylemeyen belge, onu bir kusur gibi gösterir.

## CI neden üç işletim sistemi

`capture.py` Windows'ta farklı bir yol izliyor: süreç grubu yok, boru üzerinde
seçici yok. Kimsenin çalıştırmadığı bir yol, kimsenin bilmediği bir yoldur — ve
bu proje dünya çapında kullanılmak üzere yazıldı, dolayısıyla "benim makinemde
çalışıyor" bir cevap değil.

Aynı sebeple `SIFT_LIVE` CI'da bilerek tanımsız: paket bir anahtara ya da ağa
bağımlı olmamalı. Üçüncü kural burada da geçerli.

## Bundan sonrası insan işi

Kodun yapamayacağı üç adım kaldı ve hepsi hesap sahibinin:

1. Depoyu herkese açık yap.
2. PyPI'de güvenilir yayınlayıcıyı tanımla — proje `sift-cli`, iş akışı
   `release.yml`, ortam `pypi`.
3. `v1.0.0` etiketini at.

Üçüncüsünden sonrası kendiliğinden yürür: kontroller üç işletim sisteminde
koşar, etiketle sürüm karşılaştırılır, paket kurulur ve yayınlanır.

## Bu fazın dersi

**Geri alınamayan bir işlem, kasıtlı bir jest dışında hiçbir yoldan
tetiklenmemelidir.**

Yayınlamak bu projedeki tek gerçekten geri alınamaz eylem. O yüzden bir dala
değil bir etikete bağlandı, saklanan bir jetonla değil imzalanan bir kimlikle
yapıldı, ve etiket ile sürümün aynı olduğu güvenilmek yerine ölçüldü. Bunların
hiçbiri "dikkatli olurum" ile değiştirilebilir değil: dikkat bir kez unutulur,
kural her seferinde hatırlar.
