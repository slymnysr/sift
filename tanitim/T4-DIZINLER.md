# T4 — Dizinler

**Tarih:** 9 Eylül 2026
**Durum:** bitti (buradan yapılabilecek kadarıyla; ikisi kendiliğinden gelecek)

## Plan neyi yanlış varsayıyordu

Plan dördünü de "ayrı gönderim" diye yazmıştı. Doğrusu şu: **2026'da ekosistem
resmî kayıt defterinin etrafında toplandı** ve dizinlerin çoğu artık oradan
besleniyor. Resmî duyurunun kendi cümlesi:

> primarily designed for programmatic consumption by subregistries (Smithery,
> PulseMCP, Docker Hub, Anthropic, GitHub, etc.)

Yani T2'yi yapmak, T4'ün büyük kısmını da yapmış oldu. Dördün durumu:

| dizin | yol | durum |
|---|---|---|
| **PulseMCP** | Gönderim **durdurulmuş** | Kendi sayfaları resmî kayıt defterine yayınlamayı öneriyor: *"we will pick it up automatically once we are back"* — yapılacak bir şey yok |
| **Glama** | Resmî kayıt defterini **ingest edip yeniden yayınlıyor** ("Glama is a superset of the official MCP Registry") | Kendiliğinden gelecek. Elle göndermek GitHub OAuth ister (tarayıcı) — hızlandırır, gerekmez |
| **Smithery** | Alt kayıt defteri, resmî kayıttan besleniyor | Kendiliğinden gelecek. Elle yayın hesap ister |
| **mcp.so** | GitHub issue | **Gönderildi:** [chatmcp/mcpso#4010](https://github.com/chatmcp/mcpso/issues/4010) |

## mcp.so gönderimi

Depodaki son gönderimlerin biçimine bakıp aynısını kullandım (ad, kayıt adı,
tür, depo, paket, kimlik doğrulama, lisans, kategori, kurulum satırı, açıklama,
araç listesi).

Açıklamada yalnız ölçülmüş şeyler var: 404 satırlık bir derlemede 7 satır,
%97,6 daha az token, 0 uydurma satır. Ve MCP tarafında en çok önemli olan
cümle: **anahtar yoksa araçlar reddetmiyor** — komut yine çalışıyor, çıktı yine
geliyor, çıkış kodu yine komutun kendisinin.

`list` ve `stats`'ın **bilerek** sunulmadığını da yazdım. Bir dizinde eksik
görünür; doğru olan bu: o ikisi modele bu makinede son çalıştırılan her komutu
verirdi, sormadıklarını da.

## Ne zaman bakılacak

Glama ve Smithery kendi takvimlerinde tarıyor. **13 Eylül 2026**'da bakılacak:
üçünde de (Glama, Smithery, PulseMCP) `sift` görünüyor mu, mcp.so issue'suna
cevap gelmiş mi. Sonuç `ARASTIRMA.md`'deki ölçüm tablosuna yazılacak.
