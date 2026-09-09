# Araştırma özeti — MCP ekosisteminde keşfedilebilirlik

Bu dosya İŞ 1'in hafızası. Her yeni bulgu, her ret, her ölçüm buraya yazılır.
Amacı altı ay sonra "bunu denemiş miydik" sorusunu cevaplamak.

**Son güncelleme:** 9 Eylül 2026

---

## 1. Resmî MCP kayıt defteri

**Adres:** `registry.modelcontextprotocol.io` — Eylül 2025'te önizlemede
başladı, hâlâ önizleme (kırılgan değişiklik ve veri sıfırlaması olabilir).

**Neden en önemli kanal:** İstemciler buradan okuyor ve **canlı sorgulanıyor.**
Bir modelin eğitim verisine giremeyecek kadar yeni bir paketin bulunabilmesinin
tek gerçekçi yolu bu.

### Yayınlama mekaniği

`mcp-publisher` adlı CLI ile. Komutlar: `init`, `login`, `publish`, `status`,
`validate`, `logout`.

**Kimlik doğrulama sağlayıcıları:**

| sağlayıcı | ne için |
|---|---|
| `github` | Etkileşimli OAuth (tarayıcı) |
| **`github-oidc`** | **CI/CD — GitHub Actions içinden, tarayıcısız** |
| `dns` / `http` | Alan adı doğrulama (kendi alan adın varsa) |
| `none` | Yalnız yerel test |

`github-oidc` bizim için doğru olan: yayın CI'dan yapılabilir, elle adım kalmaz.

### İsim alanı

`io.github.<kullanıcı>/<ad>` — GitHub hesabıyla kanıtlanıyor. Bizimki:
**`io.github.slymnysr/sift`**

Alan adı isim alanı (`com.example/...`) DNS TXT kaydı ya da HTTPS uç noktası
istiyor; bizim alan adımız yok, GitHub isim alanı yeterli.

### PyPI sahiplik doğrulaması — kritik

Kayıt defteri, PyPI paketinin **README'sinde** (PyPI'da açıklama olarak
görünen metin) şu dizeyi arıyor:

```
mcp-name: io.github.slymnysr/sift
```

HTML yorumu içinde gizlenebilir:

```markdown
<!-- mcp-name: io.github.slymnysr/sift -->
```

**Sonucu:** README paketin içinde yayınlandığı için, bu işaret olmadan
yayınlanmış bir sürüm doğrulanamaz. **1.0.0'da yok → yeni sürüm şart.**

> Not: crates.io HTML yorumlarını siliyor, orada görünür metin gerekiyor.
> PyPI ve NuGet yorumu koruyor. Bizde sorun yok.

### Diğer kısıtlar

- Yalnız güvenilen kayıtlar: PyPI için **yalnız `pypi.org`**
- `_meta` içinde yalnız `io.modelcontextprotocol.registry/publisher-provided`
  anahtarı korunuyor, 4 KB sınırı
- Şema: `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`

---

## 2. Üçüncü taraf dizinler

Dördü de ayrı gönderim ister; çoğu ekosistemi **tarıyor** ve sonradan sahiplik
talep etmene izin veriyor.

| dizin | ölçek | gönderim |
|---|---|---|
| **Glama** (`glama.ai/mcp`) | ~37.000 sunucu (2026 ortası) | Form, elle inceleme. Metakayıt — Anthropic, GitHub, PulseMCP, Microsoft besliyor |
| **mcp.so** | ~20.000 sunucu | Sitedeki Submit ya da GitHub issue |
| **Smithery** (`smithery.ai`) | 7.000+ | "MCP'nin Docker Hub'ı"; yerel CLI kurulumu ya da barındırılan uzak sunucu |
| **PulseMCP** | — | Gezinti çubuğunda Submit. **Haftalık ziyaretçi sayısı gösteriyor** — tek yerde bulunan bir veri |

PulseMCP'nin ziyaretçi sayacı bizim için ayrıca değerli: tanıtımın işe yarayıp
yaramadığını ölçebileceğimiz nadir bir dış gösterge.

---

## 3. awesome-mcp-servers

`punkpeye/awesome-mcp-servers` — GitHub'da PR ile eklenir.

**Şartlar:** README, açık bir açıklama, çalışan kurulum talimatı. Üçü de bizde
var (kurulum talimatı 28. fazda düzeltildi).

---

## 4. Henüz araştırılmamış / açık sorular

- **Reddit `r/ClaudeAI`, `r/mcp`** — norm ne, kendi projesini paylaşmak hoş
  karşılanıyor mu, hangi biçimde
- **Hacker News** — "Show HN" eşiği; erken paylaşım bir kez yakılan bir kart
- **dev.to / Medium yazısı** — ölçüm tablosu iyi bir yazı konusu olabilir:
  "aynı işi sift'li ve sift'siz ölçtük"
- **MCP istemcileri** — Claude Code dışında hangi istemciler kayıt defterinden
  okuyor (Cursor, Windsurf, Zed, Cline?) ve ayrı gönderim istiyorlar mı
- **GitHub Release** sayfasının keşfedilebilirliğe etkisi
- **PyPI sayfasının okunamaması** — `pypi.org/project/sift-cli/` JavaScript
  hatası veriyor, bir asistan çekmeye çalışınca boş dönüyor. README ham hâli
  çalışıyor. Bu, PyPI açıklamasının bir asistan için işe yaramadığı anlamına
  gelebilir — doğrulanmalı

---

## 5. Ölçüm — bugünün taban çizgisi

| gösterge | 9 Eylül 2026 |
|---|---|
| GitHub yıldız | 0 |
| GitHub topics | 0 |
| PyPI sürüm | 1.0.0 |
| PyPI indirme | (ölçülmedi) |
| Kayıt defteri | kayıtlı değil |
| Dizin | 0/4 |

Sonraki ölçümler buraya eklenecek.

---

## Kaynaklar

- [Introducing the MCP Registry — MCP Blog](https://blog.modelcontextprotocol.io/posts/2025-09-08-mcp-registry-preview/)
- [modelcontextprotocol/registry (GitHub)](https://github.com/modelcontextprotocol/registry)
- [MCP Registry — Package Types](https://modelcontextprotocol.io/registry/package-types)
- [Official Registry server.json Requirements](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/official-registry-requirements.md)
- [How to list your MCP server — Tallyfy](https://tallyfy.com/how-to-list-mcp-server-registry-smithery-glama-pulsemcp/)
- [Best MCP Registries in 2026 — TrueFoundry](https://www.truefoundry.com/blog/best-mcp-registries)
- [MCP Server Directories — DYNO Mapper](https://dynomapper.com/blog/ai/mcp-server-directories/)
