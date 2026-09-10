# T5 ek adımı — Glama, ve neden bir Dockerfile

**Tarih:** 10 Eylül 2026 · **Durum:** hazır, son adım kullanıcının

## Ne oldu

awesome-mcp-servers PR'ı ([#14050](https://github.com/punkpeye/awesome-mcp-servers/pull/14050))
açıldıktan sonra deponun robotu bir şart koydu:

> 1. **Ensure your server is listed on Glama.** ... you must add Dockerfile
>    directly to Glama. For checks to pass, we only need the server to start and
>    respond to introspection requests.
> 2. **Update your PR** by adding a Glama score badge after the server description.

Yani T5 artık T4'ün bir parçasına bağımlı: **Glama listesi olmadan PR
birleşmiyor.**

## Docker kararı: elenen soru bu değildi

`gelistirme/BULGULAR.md` §C'de Docker imajı elenmişti. Oradaki gerekçe
**dağıtım** hakkındaydı ve aynen duruyor:

> sift'in işi *bu* makinedeki komutu çalıştırmak; konteynerde yanlış makinenin
> çıktısını verir.

Glama'nın istediği dağıtım değil, bir **duman testi**: sunucu ayağa kalkıyor ve
`tools/list`'e cevap veriyor mu. İkisi farklı sorular, ve ikincisine "evet"
demek birincisini geri almıyor.

Bu yüzden `Dockerfile` deponun kökünde değil, **burada** duruyor. README'nin
yanında bir `Dockerfile`, "sift'i konteynerde çalıştır" daveti gibi okunur — ve
orada çalıştırmak, aracın yanlış soruyu cevaplamasının tek yolu. Dosyanın kendi
başlığı da bunu söylüyor.

İmaj ayrıca `SIFT_NO_MODEL=1` taşıyor: denetçinin kumbarasında sorulacak bir
model yok zaten, ve bu hâliyle imaj yanlışlıkla bir anahtar verilse bile ağa
çıkamaz.

## Doğrulanan ve doğrulanmayan

**Doğrulandı** (10 Eylül, bu makinede): PyPI'dan taze kurulmuş `sift-cli[mcp]`,
anahtarsız ve `SIFT_NO_MODEL=1` iken ayağa kalkıyor ve `tools/list`'e yedi aracı
künyeleriyle döndürüyor. Yani Glama'nın istediği davranış var.

**Doğrulanmadı:** imajın kendisi. Docker Desktop bu makinede kurulu ama bu WSL
dağıtımına bağlı değil (`docker` komutu yok). Yani `FROM python:3.13-slim` +
`pip install` katmanı sınanmadı — sınanan şey, o katmanın içinde koşacak olan
program.

## Kalan adım — tarayıcı gerektiriyor

1. <https://glama.ai/mcp/servers> → sunucu ekle, **GitHub OAuth** ile giriş
   (Glama, listeleyenin depoya yazma yetkisi olduğunu böyle doğruluyor)
2. `tanitim/Dockerfile`'ın içeriğini Glama'nın istediği yere yapıştır
3. Denetim geçtikten sonra PR'a puan rozeti satırı eklenecek:

```
[![OWNER/REPO MCP server](https://glama.ai/mcp/servers/OWNER/REPO/badges/score.svg)](https://glama.ai/mcp/servers/OWNER/REPO)
```

`OWNER/REPO` Glama'nın verdiği yol; listeleme yapılmadan bilinmiyor, o yüzden
şimdiden yazılmadı.
