# İŞ 1 — Popülerlik planı

## Sorun, olduğu gibi

`sift-cli` 8 Eylül 2026'da yayınlandı. Bugün itibarıyla:

| kanal | durum |
|---|---|
| Modelin eğitim verisi | Paket bir günlük. **Hiçbir model bilmiyor, bilemez** |
| GitHub | **0 yıldız, 0 topic** |
| PyPI | Yayında, ama adıyla aranmadıkça bulunmaz |
| Resmî MCP kayıt defteri | **Kayıtlı değil** |
| Dizinler (mcp.so, Glama, PulseMCP, Smithery) | Hiçbirinde yok |
| awesome-mcp-servers | Yok |

**Keşfedilebilirlik sıfır.** Bu bir kod sorunu değil; kod çalışıyor, 639 test
yeşil, üç platformda CI geçiyor. Sorun dağıtım.

## Ölçüt

Bu işin başarısı yıldız sayısıyla değil, **bir yabancının sift'e ulaşabileceği
yolların sayısıyla** ölçülür. Bugün sıfır. Hedef: bir asistanın "bağlam israfı"
sorununu duyduğunda sift'i **bulabileceği** en az beş bağımsız yol.

Yıldız ve indirme sayısı sonuç, hedef değil. Onları takip edeceğiz ama
kovalamayacağız.

## Fazlar

Her faz kendi başına bitmiş sayılır ve doğrulanabilir bir çıktısı vardır.

| # | Faz | Ne biter | Durum |
|---|-----|----------|---|
| T1 | Sürüm 1.0.1 | Kayıt defterinin şart koştuğu `mcp-name` işareti + bekleyen kod düzeltmesi, PyPI'da | bekliyor |
| T2 | Resmî kayıt defteri | `server.json`, `registry.modelcontextprotocol.io`'da yayında | bekliyor |
| T3 | GitHub keşfedilebilirliği | topics, açıklama, sürüm notu | bekliyor |
| T4 | Dizinler | mcp.so, PulseMCP, Glama, Smithery | bekliyor |
| T5 | awesome-mcp-servers | PR açık | bekliyor |
| T6 | README konumlandırma | Problem, insanların aradığı kelimelerle anılıyor | bekliyor |
| T7 | Sürekli araştırma | `ARASTIRMA.md` güncel, yeni kanallar izleniyor | sürekli |

---

## T1 — Sürüm 1.0.1

**Neden ilk:** Resmî kayıt defteri PyPI sahipliğini **paketin README'sinden**
doğruluyor. Aranan dize:

```
mcp-name: io.github.slymnysr/sift
```

HTML yorumu içinde olabilir, ama **yayınlanmış pakette bulunmak zorunda.**
1.0.0'da yok. Yani T2 T1'siz yapılamaz.

Aynı sürümde bekleyen bir düzeltme daha var (`notlar/28-KURULUM.md`):
`server.py`'deki eksik-eklenti mesajı hâlâ `pip install "sift-cli[mcp]"` diyor
ve o komut Debian/Ubuntu/WSL'de reddediliyor.

**Yapılacaklar**
- README'ye `mcp-name` işareti
- `server.py` → `NO_MCP` mesajı `uv tool install`'a
- `test_server.py` ve `mutations.py` aynı dizgeye bağlı, birlikte güncellenecek
- `pyproject.toml` sürüm 1.0.1
- Tag `v1.0.1`, CI yeşil, PyPI'da

**Bitti sayılır:** PyPI'daki 1.0.1 açıklamasında `mcp-name` dizesi görünüyor.

## T2 — Resmî MCP kayıt defteri

**Neden en önemlisi:** İstemciler oradan okuyor. Bir modelin sift'i "bilmesinin"
gerçekçi tek yolu bu — eğitim verisine giremeyecek kadar yeni, ama kayıt defteri
canlı sorgulanıyor.

**Yapılacaklar**
- `server.json`: ad `io.github.slymnysr/sift`, PyPI paketi `sift-cli`, taşıma
  `stdio`, `runtimeHint` olarak `uvx`
- `mcp-publisher` ile giriş: **`github-oidc`** tercih edilir — GitHub Action
  içinden, interaktif tarayıcı akışı olmadan. Alternatif: `login github`
- Yayınla, `registry.modelcontextprotocol.io` üzerinden doğrula

**Bitti sayılır:** Kayıt defteri API'si `io.github.slymnysr/sift`'i döndürüyor.

## T3 — GitHub keşfedilebilirliği

Beş dakikalık iş, aramada büyük fark.

- **Topics**: `mcp`, `mcp-server`, `claude`, `claude-code`, `llm`,
  `context-management`, `cli`, `python`, `token-optimization`
- Depo açıklaması ve website alanı (PyPI bağlantısı)
- `v1.0.1` için GitHub Release notu — tag var ama release sayfası yok

**Bitti sayılır:** `gh repo view` topics'i döndürüyor, Releases sayfası dolu.

## T4 — Dizinler

Dördü de üçüncü taraf, hepsi ayrı gönderim:

| dizin | yol | not |
|---|---|---|
| mcp.so | Submit düğmesi ya da GitHub issue | ~20.000 sunucu, en büyük toplayıcı |
| PulseMCP | Gezinti çubuğunda Submit | Haftalık ziyaretçi sayısı gösteriyor |
| Glama | Form, elle inceleniyor | ~37.000 sunucu izliyor, metakayıt |
| Smithery | CLI/hosted | MCP'nin Docker Hub'ı sayılıyor |

Bunların çoğu ekosistemi **tarıyor** ve sahiplik talep etmene izin veriyor —
yani T2 bittiğinde bazıları kendiliğinden görünebilir. Yine de elle göndermek
bekleme süresini kısaltır.

**Bitti sayılır:** Dördünde de gönderim yapıldı, kabul edilenler kayıtlı.

## T5 — awesome-mcp-servers

`punkpeye/awesome-mcp-servers` — PR ile eklenir. Şart: README, açık açıklama,
çalışan kurulum talimatı. Üçü de var.

**Bitti sayılır:** PR açık ve bağlantısı kayıtlı.

## T6 — README konumlandırma

Şu an README "Runs your command, then gives the model only the lines that
matter." diye başlıyor — doğru ama **kimsenin aramadığı** bir cümle.

İnsanların aradığı: *MCP token waste*, *tool output floods context*, *reduce
Claude context usage*, *agent context window full*, *MCP token optimization*.

Bu kelimeler README'de geçmiyor. Geçmeli — ama **abartmadan ve ölçümle**:
elimizde 404 satır → 7 satır, %97,6 daha az token, 0 uydurma satır gibi
gerçek sayılar var. Pazarlama dili değil, ölçüm dili.

**Bitti sayılır:** README'nin ilk ekranı problemi arama terimleriyle adlandırıyor
ve ölçülmüş bir sayı gösteriyor.

## T7 — Sürekli araştırma

`ARASTIRMA.md` bu işin hafızası. Her yeni kanal, her ret, her ölçüm oraya
yazılır. Amaç: altı ay sonra "bunu denemiş miydik" sorusunun cevabı olsun.

---

## Bu planın kuralı

**Hiçbir fazda abartı yok.** sift'in ölçülmüş sayıları var; onları söylemek
yeterli. Olmayan bir şeyi iddia etmek — "en iyi", "devrim niteliğinde", uydurma
kıyaslar — hem yanlış hem de bu projenin bütün duruşuna aykırı: araç, kaybedecek
bir şeyi olmadığı için güvenilir. Tanıtımı da öyle olmalı.
