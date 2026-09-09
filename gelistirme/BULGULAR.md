# İŞ 2 — Araştırma bulguları

Bu dosya planın **kanıt** kısmı. Her satırı ya kodun içinden ya da dış bir
kaynaktan doğrulandı; hiçbiri "iyi olurdu" diye yazılmadı.

**Tarih:** 9 Eylül 2026 · **Ölçülen sürüm:** 1.0.2 · 640 test yeşil, 5.613 satır kod

---

## A. Kodun içinden doğrulanan boşluklar

### A1. Anahtar yoksa kendi sunucun da işe yaramıyor

`model.py`:

```python
@property
def available(self) -> bool:
    return bool(self.api_key)
```

`SIFT_BASE_URL` var, `SIFT_MODELS` var — yani sift'i kendi uç noktana
yöneltebiliyorsun. Ama **yerel bir model anahtar istemez**, ve anahtar yoksa
`available` `False` dönüyor: soru hiç sorulmuyor. Ollama, llama.cpp, vLLM,
LM Studio — hepsi OpenAI şeklinde konuşur ve hiçbiri anahtar istemez.

Bugünkü davranış: `SIFT_BASE_URL=http://localhost:11434/v1` deyip anahtarı
olmayan biri, determinist yedeği alır ve nedenini `no api key` diye okur —
oysa gösterdiği sunucu orada, çalışıyor.

**Bu, benimsemenin önündeki en büyük tek engel:** bugün sift'i denemek için
NVIDIA'dan anahtar almak gerekiyor.

### A2. Araçların künyesi yok

`server.py` yedi aracı `@server.tool(name=..., description=...)` ile
tanımlıyor. Kütüphanenin (mcp 2.1.1) kabul ettiği alanlar:

```
tool(name, title, description, annotations, icons, meta, structured_output)
```

`title`, `annotations`, `structured_output` **hiç kullanılmıyor.**
`ToolAnnotations` alanları: `title`, `read_only_hint`, `destructive_hint`,
`idempotent_hint`, `open_world_hint`.

Bunun iki ayrı bedeli var:

- **İstemci tarafı:** bir istemci `readOnlyHint` gören aracı otomatik
  onaylayabilir. `peek` yerel bir dosyayı okur ve şu an `run` ile aynı
  muameleyi görür — oysa `run` **rastgele kabuk komutu çalıştırır.**
- **Dizin tarafı:** Glama bu ipuçlarını indeksliyor ("tell you whether a tool
  is safe to run in automated agent loops"). Anthropic'in kendi kılavuzu da
  adıyla anıyor: *"tool annotations help disclose which tools require
  open-world access or make destructive changes."*

### A3. `python -m sift` çalışmıyor

`src/sift/__main__.py` yok. `test/kazanc.py` yazarken buna çarpıldı; çözüm
konsol komutunu aramak oldu. Kurulu olmayan bir ortamda (CI, geçici sanal
ortam, `uvx` dışı bir kullanım) modülü çağırmak Python'da beklenen yoldur.

### A4. Boru yok

Hiçbir komut `-` almıyor (`grep '"-"' src/sift/*.py` boş döner).

```
journalctl -u nginx | sift digest -      # çalışmıyor
```

`digest` "başkasının ürettiği bir dosya" için var. Bir borudan gelen çıktı da
tam olarak odur, ve Unix'te bunun yazımı `-`'dir.

### A5. Diskin tavanı yok

`capture.py` ve `store.py` içinde tek bir boyut siniri yok. `sift run -- yes`
zaman aşımına kadar diske yazar. İkinci kural ("hiçbir şey silinmez") bir
tavanı yasaklamaz; yasakladığı şey **sessizce** silmektir.

### A6. Windows'ta ağaç bitmiyor

`test/test_background.py` içinde beş test Windows'ta atlanıyor:
*"no process groups to end there"*, *"killpg yok, yayin da yok"*.

README ise şunu diyor:

> `sift stop 9f2c41ab` — ends it, and everything it started

Windows'ta **"and everything it started" kısmı sınanmıyor**, ve `_signal`
orada `os.kill(pid, ...)` çağırıyor — yani tek süreç. Doğru mekanizma Job
Object (`CreateJobObject` + `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`), ve bu proje
27. fazda Windows için zaten ctypes kullandı.

Bu bir eksik özellikten fazlası: **yazılı bir iddianın bir platformda
sınanmaması.**

### A7. `stats` kazancı söylemiyor

`stats` şunu basıyor: yakalanan bayt, gösterilen bayt, oran, kaç istek,
**harcanan** token. Söylemediği şey: **kazanılan** token. Oysa sift her
soruşta uç noktanın `usage.prompt_tokens` değerini alıyor — yani gönderdiği
numaralı satırların token maliyeti zaten ölçülü. Kullanan kişinin sorduğu soru
"ne kadar kazandım", ve araç kendi cevabını biliyor ama basmıyor.

### A8. Depo sağlığı

Yok: `SECURITY.md`, `CONTRIBUTING.md`, issue şablonu, `CHANGELOG`.

`uv.lock` **`.gitignore`'da.** CI her koşuda uyarıyor:

> No file matched to [**/uv.lock,**/requirements*.txt]. The cache will never
> get invalidated.

Ayrıca CI uyarısı: `actions/checkout@v4` ve `astral-sh/setup-uv@v5` Node 20
hedefliyor, Node 20 kullanımdan kalkıyor.

Depo 8 Eylül'de halka açıldı ve **rastgele kabuk komutu çalıştıran** bir araç.
Güvenlik politikası burada süs değil.

### A9. Mutasyon bataryası uçtan uca hiç çalışmadı

`test/mutations.py` 182 kural taşıyor. Tek tek ve gruplar hâlinde çalıştırıldı;
**tamamı bir kez baştan sona çalıştırılmadı** (her kural bir suite koşusu ≈ 66
sn → ~3,5 saat). Yakalanmamış bir kural, korumasız bir kural demektir ve şu an
kaç tane olduğunu bilmiyoruz.

---

## B. Dışarıdan doğrulanan fırsatlar

### B1. MCP spesifikasyonu bizden ilerde

Güncel revizyon **2026-07-28**. Kurulu kütüphane (`mcp` 2.1.1) onu destekliyor.
sift'in kullanmadığı, işine yarayacak olanlar:

| yetenek | sift'e ne katar |
|---|---|
| **Tool annotations** | A2 |
| **Structured output** | Sonuç metni aynı kalır, yanına `handle`, `exit`, `shown/total`, `model` alanları düşer. Ajan çıkış kodunu düzyazıdan çıkarmak zorunda kalmaz |
| **Progress notifications** | 5 dakikalık bir `run` şu an sessiz; istemci asıldı sanır |
| **Resource links** | Sonuç, yakalamayı bir kaynak olarak gösterebilir |
| `title`, `icons`, `_meta` | Görünürlük, küçük |

### B2. Anthropic'in araç yazma kılavuzu

*Writing effective tools for AI agents* — iki maddesi doğrudan bize bakıyor:

- Araç açıklamaları bağlama yükleniyor, **küçük iyileştirmeler büyük fark
  yapıyor** (bizde açıklamalar zaten uzun ve iyi)
- **Hata cevapları eyleme dönüştürülebilir olmalı**, opak kod ya da yığın izi
  değil (bizde zaten öyle — 28. fazın bütün konusu buydu)
- **Tool annotations** açıkça öneriliyor (A2)

Yani kılavuzun üç maddesinden ikisi bizde zaten var; eksik olan tam da A2.

### B3. Yerel modeller ve OpenAI-uyumluluk

Ollama (`/v1`), llama.cpp (`--api`), vLLM, LM Studio, LocalAI — hepsi
`POST /v1/chat/completions` konuşuyor ve hiçbiri anahtar istemiyor. sift'in
istemcisi zaten düz OpenAI şekli. Yani A1'i çözmek yeni bir taşıyıcı yazmak
değil, **bir koşulu düzeltmek**.

> Bu makinede kurulu bir yerel model sunucusu yok (`ollama`, `llama-server`,
> `vllm` — üçü de yok, 11434 kapalı). Yani bu iş **şeklin** sınanmasıyla
> yapılabilir (yerel bir taklit sunucu, `test/wire.py` zaten bunun için var);
> belirli sunucuların kendisi burada koşturulmadı ve öyle olduğu yazılacak.

---

## C. Değerlendirilip elenenler

| fikir | neden hayır |
|---|---|
| **Resources: her yakalama bir kaynak** | Modele bu makinede çalışmış her komutu listelemek olur. `list` ve `stats`'ı MCP'de sunmama kararının aynısı |
| **Elicitation** | sift kullanıcıya soru sormaz; sorarsa fail-open kuralını çiğner |
| **Docker imajı** | sift'in işi *bu* makinedeki komutu çalıştırmak; konteynerde yanlış makinenin çıktısını verir |
| **Kendi modelini eğitmek / ince ayar** | Projenin tek cümlelik ekonomisi "ücretsiz olanı çalıştır"; eğitim onu bozar |
| **Sorunun cevabını akıtmak (streaming)** | Cevap zaten yalnız satır numaraları — birkaç düzine token. Akıtacak bir şey yok |
