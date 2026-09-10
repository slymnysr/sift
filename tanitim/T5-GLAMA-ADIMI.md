# T5 ek adımı — Glama, ve gerekmediği anlaşılan bir Dockerfile

**Tarih:** 10 Eylül 2026 · **Durum:** bitti, hiçbir gönderim yapılmadan

## Robotun şartı

awesome-mcp-servers PR'ı ([#14050](https://github.com/punkpeye/awesome-mcp-servers/pull/14050))
açıldıktan sonra deponun robotu iki şey istedi:

> 1. **Ensure your server is listed on Glama.** ... you must add Dockerfile
>    directly to Glama. For checks to pass, we only need the server to start and
>    respond to introspection requests.
> 2. **Update your PR** by adding a Glama score badge after the server description.

## Yaptığım fazladan iş

Birinci şartı okuyup Glama'ya elle gönderim yapılacağını varsaydım. Bir
`Dockerfile` yazdım, depo kökü yerine `tanitim/`'e koydum (kökte durursa
"sift'i konteynerde çalıştır" daveti gibi okunur, ve orada çalıştırmak aracın
yanlış makinenin çıktısını vermesinin tek yolu), `SIFT_NO_MODEL=1` ekledim, ve
konteynersiz doğrulayabildiğim kadarını doğruladım.

**Hiçbirine gerek yoktu.**

## Olan şey

Kullanıcı Glama'ya girdiğinde karşısına çıkan seçenekler benim tarif ettiklerim
değildi. Bakınca sebebi görüldü: **sift Glama'da çoktan listelenmişti.**

```
https://glama.ai/mcp/servers/slymnysr/sift
kalite: A · bakım: A · kategori: Command Line · lisans: MIT
```

Sebep `ARASTIRMA.md`'de zaten yazılıydı ve ben onu bu adımda kullanmayı
akıl etmedim: **Glama kendini resmî kayıt defterinin üst kümesi ilan ediyor**
(*"Glama ingests and re-publishes everything in the official registry"*). T2'de
`io.github.slymnysr/sift` kayıt defterine girdiği için Glama onu kendiliğinden
almış — gönderim yok, OAuth yok, Dockerfile yok.

Dockerfile silindi. Gereksiz bir dosyayı "zararı yok" diye bırakmak, onu yazma
gerekçesiyle çelişirdi: o dosyanın kendi başlığı, var olma sebebinin tek bir
denetim olduğunu söylüyordu. O denetim hiç sorulmadı.

## T4'ün tezi ölçüldü

T4 şunu iddia etmişti: *"T2'yi yapmak T4'ün dörtte üçünü de yapar, çünkü
dizinler resmî kayıttan besleniyor."* O gün bu bir okumaydı; şimdi **ölçüm**:

| dizin | ne oldu | süre |
|---|---|---|
| **Glama** | Kendiliğinden listeledi, A/A puanladı | ~1 gün |
| PulseMCP | Gönderim durdurulmuş, kayıttan alacağını söylüyor | bekliyor |
| Smithery | Alt kayıt defteri | bekliyor |
| mcp.so | Elle gönderim gerekti (issue #4010) | açık |

## Rozet

Girdiye eklendi, deponun kendi biçimine uyarak depo bağlantısının hemen ardına:

```
[![slymnysr/sift MCP server](https://glama.ai/mcp/servers/slymnysr/sift/badges/score.svg)](https://glama.ai/mcp/servers/slymnysr/sift)
```

PR `MERGEABLE` durumda ve iki şartın ikisi de karşılandı; kalan tek şey
bakımcının birleştirmesi.
