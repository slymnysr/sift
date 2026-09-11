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


---

# D. Sonradan eklenen bulgu — 11 Eylül 2026

Bu bölüm plan yazıldıktan sonra eklendi. Kaynağı bir ölçüm değil, **bir oturumun
kendisi**: sift'in tasarlandığı ajan (bu oturumdaki Claude) üç gün boyunca sift
ile çalıştı ve nasıl davrandığı gözlemlendi. Böyle bir veri nadir, o yüzden
yazıldı.

## D1. Sunucu talimatı kendini uygulatmıyor — ölçülmüş vaka

`server.py`'nin `INSTRUCTIONS` metni şunu diyor:

> Use `run` in place of a plain shell tool whenever a command may print more
> than a few dozen lines.

**Bu oturumda sift'in MCP araçları bir kez bile çağrılmadı.** Talimat bağlamda
duruyordu, araçlar yüklü ve görünürdü, ajan yine de her seferinde Bash'e gitti.

Sebep ajanın ihmali değil, **seçimin biçimi**: Bash her işe uyuyor ve
düşünmeden uzanılıyor; özel araç fark edilmeyi, tartılmayı ve çağrılmayı
istiyor. Tek bir kararın içinden bakınca özel araç bir maliyet gibi görünüyor.

### Bedeli ölçüldü: üç kez yeniden çekim

Ajan sift'in işini elle yaptı — ama **yanlış uçtan**. Her Bash çağrısı
`| tail -3`, `| head -20`, `| grep -E …` ile bitti. Yani seçim **çıktı
görülmeden** yapıldı, ve seçilmeyen kayboldu:

| ne oldu | bedeli |
|---|---|
| CI hatası `grep -iE "FAILED\|assert\|Error"` ile arandı, desen yetmedi | **İkinci çekim** gerekti |
| Batarya logunun üstünden dört ayrı `grep`/`tail` geçti | Dört geçiş, tek dosya |
| `pytest \| tail -3` özeti verdi, kırılan testi göstermedi | Tekrar bakıldı |

sift'te bu üçü olmazdı: ham çıktı diskte kalır, seçim içeriğe bakılarak yapılır,
`peek` atılanı geri getirir. **Elle filtre kör ve geri alınamaz; sift'in seçimi
gören ve geri alınabilir.**

### Yanlış okunmaması için: bu bir token iddiası değil

`grep`/`head` kabukta çalışıyor, yani elenen satırlar bağlama **hiç girmiyor**.
Ajan onların token'ını ödemiyor. Dolayısıyla **doğru tahmin edilen tek bir
denemede boru ile sift maliyet olarak eşittir** — hatta sift bir model çağrısı
eklediği için pahalıdır.

Yukarıdaki üç vakanın bedeli elenen çıktı değil, **fazladan tur**: her yeniden
çekim, bütün konuşmanın yeniden gönderilmesi demek. Bu oturumda bağlam ~732 bin
token olduğu için bir tur, önbellekli hâliyle bile ~73 bin token'lık bir yüke
denk geliyordu.

sift'in `grep` karşısındaki iddiası bu yüzden tasarruf değil, üç başka şey:

1. **Tahmin gerekmiyor.** `grep -iE "FAILED|assert|Error"` uydurulmuş bir desen;
   hata o kelimeleri içermiyorsa boş döner, ve boş dönmesi "hata yok" ile aynı
   görünür.
2. **Gösterilmeyen geri gelir** — komutu yeniden çalıştırmadan.
3. **Yeniden çalıştırmak aynı şeyi vermeyebilir.** Sabit bir log okunuyorsa
   şans; bir derleme ya da test tekrar koşturulduğunda hata hiç tekrarlamayabilir.

## D2. `MUST` eklenmesin — gerekçe projenin kendi içinde yazılı

Karşılaştırma için: `context7` araç açıklamasında **MUST** kullanıyor
(*"You MUST call resolve-library-id before get-library-docs"*) ve işliyor,
çünkü orada **prosedürel bir bağ** var — atlarsan geçerli kimlik olmaz, araç
hata verir. Kural sınanabilir.

"Bash yerine sift kullan" ise bir **yargı sınırı**, ve `hook.py`'nin ilk
paragrafı bu sınıfı zaten reddetmiş:

> A list of commands worth intercepting is a list of tools wearing a disguise…
> And it cannot be right in principle — **how much a command prints is not
> knowable before it runs.**

MUST, o reddedilen şeyin bir kat üstü: ajandan komut çalışmadan önce karar
vermesini istiyor. Üstelik `git rev-parse HEAD` için apaçık yanlış, ve bazı
yerde apaçık yanlış olan mutlak bir kural haklı olduğu yerlerde de ıskartaya
çıkıyor.

## D3. Asıl mesele: okunan şey zaten ödenmiştir

Bu oturumda ortaya çıkan en keskin cümle, aracın niye var olduğunu da
açıklıyor.

Bir ajanın "çıktıyı kendim özetliyorum" demesi **maliyet açısından bir
yanılsama**. Okuduğu her şey o anda bağlama girmiştir ve ödenmiştir; üstüne
özet yazmak toplamı **artırır**, çünkü ham çıktı hâlâ oradadır ve sonraki her
turda yeniden gönderilir. Bir ajan **okuduğu şeyi geri alamaz.**

Maliyeti gerçekten düşüren iki şey var:

1. **İçeri hiç almamak** — `tail`/`grep` ile önceden kesmek. Kör ve geri
   alınamaz (D1).
2. **Konuşmanın dışındaki bir şeyin okuyup yalnız seçimi içeri vermesi** —
   sift. Ham bayt transkripte hiç girmez.

İkinci fark ise doğrulukta: ajanın yaptığı **özet**, yani uydurulmuş metin ve
içeriği hakkında yanlış olabilir. sift'in yaptığı **seçim**: satırı yazmıyor,
seçiyor, o yüzden ne dediği konusunda yanılamaz — yalnız neyin önemli olduğu
konusunda yanılabilir, ve atılanı `peek` geri getirir.

## D4. Bundan çıkan iş (yapılmadı, karar bekliyor)

- **`sift hook --install`** bu bulgunun doğal sonucu ve 18. faz zaten bunun
  için yazılmış: hatırlamaya hiç sormuyor. Bu oturumda kurulsaydı üç yeniden
  çekim olmayacaktı.
- Alternatif ve daha zayıfı: kullanıcının `CLAUDE.md`'sine bir satır —
  kullanıcının kuralları sunucunun talimatından daha ağır basıyor.
- **`MUST` eklenmesin** (D2).
- İncelenebilir: kısa çıktıda hook'un gerçekten model çağrısı yapmadığı
  doğrulanmalı. Docstring *"twelve lines in, twelve lines out"* diyor; bu
  ölçülmedi.
