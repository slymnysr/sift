# G9 — Depo sağlığı

**Tarih:** 9 Eylül 2026 · **Durum:** bitti

Depo 8 Eylül'de halka açıldı. Bu faz, açık bir depoda **yabancının ilk baktığı
şeylerin** eksik olmasını kapatıyor.

## `SECURITY.md`

Bu araç kabuk komutu çalıştırıyor ve dışarı metin gönderiyor. İkisi de düz bir
cevabı hak ediyor, ve dosya tam olarak o: ne çalışıyor, ne çıkıyor, nereye
bildirilir.

İçindeki üç şey süs değil:

- **`run` ve `tool` künyelerinde yıkıcı ilan edildi** (G2) ve dosya bunun
  sebebini yazıyor: `run` rastgele komut satırı çalıştırıyor, `tool`
  argümanlarını `ast-grep`'e olduğu gibi geçiriyor ve o istenirse dosya yazıyor.
- **Maskeleme tam değil**, ve dosya bunu iddia etmiyor. Garantili olan tek şey
  `SIFT_NO_MODEL=1`.
- **Yakalamalar şifreli değil.** Bir sır basmış komutun sırrı diskte, yalnız
  senin okuyabileceğin bir dosyada duruyor — kabuğun onu `~/.bash_history`'ye
  yazmasıyla aynı şey, ve bilinmeye değer.

Ayrıca neyin **açık olmadığı** yazılı: `sift run`'ın kendisine verilen komutu
çalıştırması bir güvenlik açığı değil.

## `CONTRIBUTING.md`

Bu deponun alışılmadık tarafları var ve hiçbiri tercih değil; her biri o
olmadığında bir şey ters gittiği için orada:

- **İki dil.** Notlar Türkçe, kod ve yorumlar İngilizce. Katkı için Türkçe
  gerekmiyor ve bu yazıyor.
- **Üç kural.** Birini zayıflatarak bir şeyi iyileştiren PR reddedilir, ve
  gerekçesi bu liste olur.
- **Her kural bir mutasyon.** Kaçan mutasyon bir bulgudur, formalite değil. Bu
  projede batarya **üç kez** bir *testin* hiçbir şey kanıtlamadığını gösterdi:
  sınanan şey olmadan biten bir komut, kendisiyle eşleşen bir sorgu, dala hiç
  varmayan bir girdi. Bu da yazılı — gelen kişi kendisininkini de beklesin.
- **Ölçmediğin sayıyı yazma.** Baytı dörde bölmek token sayısı değil.
- **Kıramadığın kural için mutasyon ekleme**; hangi CI ayağının koruduğunu yaz
  (G7'de tam olarak bu oldu).

## `uv.lock` artık izleniyor

`.gitignore`'daydı. İki bedeli vardı, biri görünür:

```
No file matched to [**/uv.lock,**/requirements*.txt].
The cache will never get invalidated.
```

CI her koşuda bunu uyarıyordu — yani bağımlılık önbelleği hiçbir zaman
geçersizleşmiyor, her koşu her şeyi yeniden çözüp indiriyordu. Görünmeyen bedel
ise tekrarlanabilirlik: kimsenin yazmadığı bir çözüm, tekrarlanamayan bir build.

Bir test bunu tutuyor ve bataryada bir kuralı var: `.gitignore`'a `uv.lock`
geri konursa test kırmızı döner.

## Action sürümleri

CI her koşuda Node 20'nin kalktığını söylüyordu. Beşi de güncellendi:

| action | önce | sonra |
|---|---|---|
| `actions/checkout` | v4 | v7 |
| `astral-sh/setup-uv` | v5 | **v10.0.1** |
| `actions/upload-artifact` | v4 | v7 |
| `actions/download-artifact` | v4 | v8 |
| `pypa/gh-action-pypi-publish` | `release/v1` | değişmedi (hareketli etiket kasıtlı) |

Sürümler tahminle değil, `gh api repos/<r>/releases/latest` ile okundu — ama
**etiketin biçimi** tahmin edildi ve CI onu düzeltti.

`actions/*` büyük sürüm takma adı yayınlıyor (`v7`, `v8`); `astral-sh/setup-uv`
yayınlamıyor, etiketleri yalnız tam sürüm (`v10.0.1`, `v9.0.0`). `@v10` hiçbir
şeye çözülmüyor ve CI'ın **beş ayağı da tek satır çalıştırmadan** düşüyor.
Doğrulaması `gh api repos/<r>/tags` — biri okundu, öteki varsayıldı, ve ikisi
aynı komutla okunabilirdi.

Bu yüzden tam sürüme sabitlendi, ve neden sabitlendiği iş akışının içinde yazılı.
