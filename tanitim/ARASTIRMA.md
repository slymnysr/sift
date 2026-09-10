# Araştırma özeti — MCP ekosisteminde keşfedilebilirlik

Bu dosya İŞ 1'in hafızası. Her yeni bulgu, her ret, her ölçüm buraya yazılır.
Amacı altı ay sonra "bunu denemiş miydik" sorusunu cevaplamak.

**Son güncelleme:** 11 Eylül 2026 (bulut rutini denendi, ağ çıkışı kapalı çıktı, kapatıldı)

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
yayınlanmış bir sürüm doğrulanamaz. 1.0.0'da yoktu; **1.0.1'de eklendi ve
PyPI'daki açıklamada doğrulandı.**

> Not: crates.io HTML yorumlarını siliyor, orada görünür metin gerekiyor.
> PyPI ve NuGet yorumu koruyor. Bizde sorun yok.

### Komutun adı — belgede yazmayan kısıt

Bir istemci girdiden komutu şu sırayla kuruyor (kayıt defterinin Snyk örneği):

```
<runtimeHint> <runtimeArguments...> <identifier> <packageArguments...>
```

`identifier` PyPI paket adı olmak zorunda (sahiplik oradan doğrulanıyor). Yani
`uvx <paket adı>` çalışmalı — **konsol komutunun adı paketin adı olmalı.**
Hiçbir belgede yazmıyor; kayıt defterindeki 627 PyPI paketinden yalnız 5'i
`--from` kullanıyor, gerisi bu varsayıma uyuyor.

Bizde uymuyordu (`sift` PyPI'da alınmış, paket `sift-cli`, komutlar `sift` ve
`sift-mcp`). 1.0.2'de `sift-cli` konsol komutu ve `sift mcp` alt komutu
eklendi. Ayrıntı: `tanitim/T2-KAYIT-DEFTERI.md`.

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

### Düzeltme — 9 Eylül 2026: dördü de "ayrı gönderim" değil

Yukarıdaki tablo 2025 mantığıyla yazılmış. 2026'da ekosistem resmî kayıt
defterinin etrafında toplandı; resmî duyurunun kendi cümlesi kayıt defterinin
*"primarily designed for programmatic consumption by subregistries (Smithery,
PulseMCP, Docker Hub, Anthropic, GitHub, etc.)"* olduğunu söylüyor.

- **PulseMCP** gönderimi tamamen durdurmuş; sayfası resmî kayda yayınlamayı
  öneriyor, *"we will pick it up automatically once we are back"*
- **Glama** kendini resmî kaydın üst kümesi ilan ediyor, ingest edip yeniden
  yayınlıyor. Elle gönderim GitHub OAuth ister (tarayıcı)
- **Smithery** alt kayıt defteri, aynı kaynaktan besleniyor. Elle yayın hesap ister
- **mcp.so** hâlâ elle: GitHub issue (`chatmcp/mcpso`)

Sonuç: T2 yapıldıysa T4'ün dörtte üçü kendiliğinden oluyor. Ayrıntı:
`tanitim/T4-DIZINLER.md`.

---

## 3. awesome-mcp-servers

`punkpeye/awesome-mcp-servers` — GitHub'da PR ile eklenir.

**Şartlar:** README, açık bir açıklama, çalışan kurulum talimatı. Üçü de bizde
var (kurulum talimatı 28. fazda düzeltildi).

---

## 4. Araştırıldı — 9 Eylül 2026

### GitHub MCP Registry ve VS Code — beklenmedik kazanç

En değerli bulgu. VS Code'un **`MCP: Browse Servers`** komutu sunucu listesini
**GitHub MCP Registry**'den çekiyor. Ve GitHub'ın kendi duyurusu:

> developers will be able to self-publish MCP servers directly to the OSS MCP
> Community Registry. Once published, those servers will **automatically appear
> in the GitHub MCP Registry**

Yani T2, ayrıca VS Code + Copilot kullanıcılarına da açılan kapıyı açtı. Ayrı
gönderim yok. **13 Eylül'de doğrulanacak:** `github.com/mcp` aramasında sift
görünüyor mu.

### PyPI sayfası — sorun JavaScript değil, bot duvarı

Önceki notta "JavaScript hatası" diye yazılmıştı. Değil: `pypi.org/project/
sift-cli/` bir tarayıcı olmayan istemciye **3 KB'lık "Client Challenge"
sayfası** dönüyor. Tarayıcı `User-Agent`'ı taklit etmek de yetmiyor.

| yüzey | bir asistan okuyabiliyor mu |
|---|---|
| `pypi.org/project/sift-cli/` (HTML) | **hayır** — Client Challenge |
| `pypi.org/pypi/sift-cli/json` | **evet** — açıklama tam metin geliyor |
| GitHub README | evet |
| Kayıt defteri API'si | evet |

**Sonuç:** PyPI açıklamasına yazılan hiçbir şey, bir asistan tarafından HTML
sayfasından okunamaz. Kayıt defterinin `mcp-name` doğrulaması JSON API'yi
kullandığı için bizi etkilemiyor — ama "asistan PyPI sayfasını okur" varsayımına
dayanan hiçbir plan yapılmamalı.

### Reddit ve Hacker News — bizim yapmayacağımız iş

İkisi de **kullanıcının kendi kararı ve kendi kimliğiyle** yapılacak işler; bir
ajanın topluluk hesabından paylaşım yapması doğru değil. Araştırma yine de
duruyor, çünkü karar verilirse biçimi belli olsun:

- **`r/mcp`** — MCP'nin en büyük iki topluluğundan biri (diğeri Discord).
  Sunucu yazarları için `mcp-server-authors` etiketi var; moderatörleri
  etiketleyip ne yaptığını söylemek beklenen davranış
- **Show HN** — başlık `Show HN:` ile başlamalı, reklam dili başlığı
  değiştirtir. İlk yorum yapımcının kendi yorumu olmalı: neden yazıldı, neyle
  yazıldı, **ve dürüst bir sınır**. Salı–Perşembe 09:00–12:00 ET. İlk 60 dakika
  yorumlara cevap vermek gerekiyor — yani boş bir saatte atılmamalı
- **Bir kez yakılan kart:** Show HN bir projeyi bir kez tanıtır. sift'in
  bugünkü hâli iyi ama yıldızı sıfır; birkaç haftalık gerçek kullanım ve
  cevaplanmış birkaç issue sonrası daha güçlü bir kart olur

### Değerlendirilip elenen kanallar

- **Docker MCP Catalog** (`docker/mcp-registry`, PR ile) — sift'in işi
  **bu makinedeki komutu çalıştırmak.** Konteyner içinde çalıştırılırsa yanlış
  makinenin çıktısını verir. Teknik olarak mümkün, kavramsal olarak yanlış:
  eklenmedi
- **Anthropic connector dizini** — uzak (remote) bağlayıcılar için. sift yerel
  stdio; uygun değil

### Hâlâ açık

- **dev.to / Medium yazısı** — ölçüm tablosu iyi bir yazı konusu:
  "aynı işi sift'li ve sift'siz ölçtük". Zamanlama Show HN ile birlikte
  düşünülmeli
- **GitHub Release sayfasının** keşfedilebilirliğe ölçülebilir etkisi

---

## 5. Ölçüm — bugünün taban çizgisi

| gösterge | 9 Eylül (sabah) | 9 Eylül (İŞ1 sonu) |
|---|---|---|
| GitHub yıldız | 0 | 0 |
| GitHub topics | 0 | **12** |
| GitHub release sayfası | 0 | **3** |
| Depo açıklaması | "MCP" geçmiyor | **"MCP server and CLI…"** |
| PyPI sürüm | 1.0.0 | **1.1.0** |
| PyPI indirme | (ölçülmedi) | (ölçülmedi) |
| Kayıt defteri | kayıtlı değil | **`io.github.slymnysr/sift`, active** |
| GitHub MCP Registry | yok | kayıttan besleniyor — 13 Eyl'de bakılacak |
| mcp.so | yok | [issue #4010](https://github.com/chatmcp/mcpso/issues/4010) |
| Glama / Smithery / PulseMCP | yok | kayıttan besleniyor — 13 Eyl'de bakılacak |
| awesome-mcp-servers | yok | [PR #14050](https://github.com/punkpeye/awesome-mcp-servers/pull/14050) |

**Bir yabancının sift'e ulaşabileceği bağımsız yol sayısı: 0 → 6**
(resmî kayıt defteri, GitHub MCP Registry/VS Code, mcp.so, Glama, Smithery,
awesome-mcp-servers) — dördü hâlâ tarama bekliyor.

Sonraki ölçümler buraya eklenecek.

### Erken kontrol — 9 Eylül 2026 akşamı

Liste 13 Eylül için yazılmıştı; İŞ2 biterken dört gün erken bakıldı. **Dizin
taramaları henüz gelmemiş olabilir**, o yüzden aşağıdaki "yok"lar bir sonuç
değil, bir taban çizgisi.

| kanal | durum | not |
|---|---|---|
| Resmî kayıt defteri | **`active`, 1.1.0, isLatest** | İŞ2 biterken 1.1.0 yayınlandı; kayıt defteri iş akışı kendiliğinden güncelledi |
| GitHub | 0 yıldız, 0 fork, 0 izleyen | Bir günlük |
| **PyPI indirme** | **83** aynasız / 222 aynalı | Kırılımı aşağıda — 83'ün 75'i kurulum bile değil |
| mcp.so [#4010](https://github.com/chatmcp/mcpso/issues/4010) | Açık, bakım cevabı yok | Tek yorum bizim düzeltmemiz |
| awesome-mcp-servers [#14050](https://github.com/punkpeye/awesome-mcp-servers/pull/14050) | **Açık ve engellenmiş** | Aşağıda |
| PulseMCP API | `sift` dönmüyor | Gönderim zaten durdurulmuş |
| Glama | **listelendi: A/A** | 10 Eylül'de görüldü; hiçbir gönderim yapılmadı — kayıt defterinden geldi |
| `github.com/mcp` | Sayfa JavaScript'le çiziliyor | Buradan doğrulanamadı |

### "83 indirme" ne değil

PyPI'ın indirme dediği şey bir **HTTP isteği**, bir kurulum değil. Gerçek bir
`pip`/`uv` kurulumu kendini tanıtır: User-Agent'ında Python sürümünü ve
işletim sistemini söyler. Ölçülen kırılım:

| | |
|---|---|
| Aynalar dahil | 222 |
| Aynalar hariç | 83 |
| Python sürümü bildirilmeyen | **75** |
| Bir kurucudan gelen | **8** (Linux; 3.12'den 6, 3.14'ten 1, 3.9'dan 1) |

75 istek hiçbir şey söylemiyor — bot, tarayıcı, güvenlik taraması ya da düz bir
çekim. Kalan 8'in bir kısmı da bizim: kayıt defterindeki komut doğrulanırken
bu makineden `uvx` çalıştırıldı (Linux, 3.12). Ve **3.9'dan gelen istek hiç
kuramaz**, çünkü paket 3.12 istiyor — yani o bir kullanıcı değil, sürüm çözen
bir otomat.

Sonuç: bir günlük pakette gerçek kullanıcı pratik olarak sıfır. Bu bir sinyal
değil, taban çizgisi — ve çıplak "83" yazmak onu sinyal gibi gösterirdi.

Kaynak: `pypistats.org/api/packages/sift-cli/{recent,overall,python_minor,system}`.

### awesome-mcp-servers artık Glama'ya bağlı — beklenmedik kapı

PR'a bir robot yorum düştü ve şart açık:

> 1. **Ensure your server is listed on Glama.** ... note: you must add Dockerfile
>    directly to Glama. For checks to pass, we only need the server to start and
>    respond to introspection requests.
> 2. **Update your PR** by adding a Glama score badge after the server description.

Yani T5, T4'ün bir parçasına bağımlı hâle geldi: **Glama listesi olmadan PR
birleşmiyor.** Ve Glama'ya elle gönderim GitHub OAuth istiyor — tarayıcı, yani
kullanıcının kendi eylemi.

Bir de şu var, ve karar kullanıcının: Glama'nın denetimi bir **Dockerfile**
istiyor. `BULGULAR.md` §C'de Docker imajı elenmişti — ama oradaki gerekçe
*dağıtım* hakkındaydı ("sift'in işi bu makinedeki komutu çalıştırmak;
konteynerde yanlış makinenin çıktısını verir"). Glama'nınki dağıtım değil, bir
duman testi: sunucu ayağa kalkıyor ve `tools/list`'e cevap veriyor mu. İkisi
farklı sorular, ve ikincisine "evet" demek birincisini geri almıyor.

**Sonra ne oldu (10 Eylül):** ikisine de gerek kalmadı. Glama sift'i
kendiliğinden listeledi — `glama.ai/mcp/servers/slymnysr/sift`, kalite A, bakım
A — çünkü kendini resmî kayıt defterinin üst kümesi ilan ediyor ve T2 onu oraya
koymuştu. Rozet PR'a eklendi, iki şart da karşılandı, Dockerfile silindi.

**Ölçülmüş sonuç:** T4'ün tezi ("dizinler kayıttan besleniyor, T2 işi yapar")
en az bir dizin için **~1 günde** doğrulandı. Ayrıntı: `T5-GLAMA-ADIMI.md`.

### 10 Eylül kontrolü — bir gün sonra

| kanal | 9 Eylül | 10 Eylül |
|---|---|---|
| Kayıt defteri | 1.1.0 · active · isLatest | değişmedi |
| **Glama** | listelendi, A/A | değişmedi — rozet PR'a eklendi |
| Smithery | yok | **yok** (arama `SiftDB` ve `BirdSift` döndürüyor, bizimki değil) |
| PulseMCP | yok | **yok** — gönderim durdurulmuş, beklenen bu |
| `github.com/mcp` | okunamadı | **okunamadı** (sayfa JavaScript'le çiziliyor) |
| GitHub | 0 yıldız | **0 yıldız, 0 fork** |
| mcp.so #4010 | açık, cevap yok | **açık**, cevap yok |
| awesome #14050 | açık, engellenmiş | **açık, `MERGEABLE`** — iki şart karşılandı |
| PyPI (aynasız toplam) | 83 | **434** |
| PyPI (kurucudan gelen) | 8 | **119** |

**PyPI'daki artışı okumanın doğru yolu.** 434'ün 315'i Python sürümü
bildirmiyor: bot, tarayıcı, ayna. Kalan 119'un dağılımı:

```
3.12: 84   3.11: 14   3.13: 13   3.14: 4   3.9: 4
```

Paket **Python >=3.12** istiyor. Yani `3.9` ve `3.11`'den gelen **18 istek hiç
kuramaz** — onlar da kullanıcı değil, sürüm çözen otomatlar. Geriye en fazla 101
kalıyor, ve onun bir kısmı da bizim: bugün Glama doğrulaması ve kayıt defteri
komutu için bu makineden `uvx` çalıştırıldı (Linux, 3.12/3.13).

Dürüst özet: 1.1.0 yayınlandı, bir dizin (Glama) kendiliğinden aldı, **gerçek
kullanıcı hâlâ ölçülebilir değil.** Bir günlük bir pakette beklenen bu.

### 13 Eylül 2026'da bakılacaklar

- `github.com/mcp` — sift göründü mü
- Glama, Smithery, PulseMCP — tarama geldi mi
- mcp.so issue #4010 — cevap/kabul
- awesome-mcp-servers PR #14050 — birleşti mi
- PyPI indirme sayısı (`pypistats`), GitHub yıldız

### Denendi ve olmadı: bulut rutini bu işi yapamıyor

10 Eylül'de bu kontrolü bir bulut rutinine bağladım
(`trig_01BwSMKGj6ZB5PAyv2JvmNhB`). **Çalışmadı, ve sebebi ölçüldü.**

Rutin 13 Eylül'e kurulmuştu; **10 Eylül 21:42'de** koştu — neden erken
tetiklendiğini bilmiyorum. Asıl mesele o değil. Koşunun kendi çıktısı:

```
Glama            HTTP:000     (bağlantı hiç kurulamadı)
PulseMCP         HTTP:000
pypistats        HTTP:000
Smithery         HTTP:000
api.github.com   HTTP:403
github.com/mcp   HTTP:403
kayıt defteri    HTTP:200     ← dokuzda tek çalışan
```

Beş ayrı sunucuya `000` dönerken birine 200 dönmesi geçici bir arıza değil:
**bulut kumbarasının ağ çıkışında bir izin listesi var** ve içinde yalnız
`registry.modelcontextprotocol.io` var. Koşu da orada takıldı; son olayından 12
saat sonra hâlâ "running" görünüyordu.

Ayrıca depo erişimi de yoktu: GitHub hesabı bulut tarafına bağlı olmadığı için
`sources` içeren rutin **401** ile reddedilmişti, o yüzden zaten deposuz
kurulmuştu.

**Sonuç:** rutin kapatıldı (`enabled: false`). Bu ölçüm **yerel oturumda**
yapılacak — dokuz kanalın dokuzu da buradan okunabiliyor, ve 9/10 Eylül
kontrolleri zaten öyle yapıldı.

**Genel ders:** bulut rutini dış dünyayı ölçmek için değil, kendi deposunda iş
yapmak için uygun. Ölçüm işini oraya vermeden önce o kumbaranın neye
ulaşabildiğini sınamak gerekiyor — burada bir gün kaybedilmedi çünkü rutin
erken koştu ve kendini ele verdi.

---

## Kaynaklar

- [Introducing the MCP Registry — MCP Blog](https://blog.modelcontextprotocol.io/posts/2025-09-08-mcp-registry-preview/)
- [modelcontextprotocol/registry (GitHub)](https://github.com/modelcontextprotocol/registry)
- [MCP Registry — Package Types](https://modelcontextprotocol.io/registry/package-types)
- [Official Registry server.json Requirements](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/official-registry-requirements.md)
- [How to list your MCP server — Tallyfy](https://tallyfy.com/how-to-list-mcp-server-registry-smithery-glama-pulsemcp/)
- [Best MCP Registries in 2026 — TrueFoundry](https://www.truefoundry.com/blog/best-mcp-registries)
- [MCP Server Directories — DYNO Mapper](https://dynomapper.com/blog/ai/mcp-server-directories/)
