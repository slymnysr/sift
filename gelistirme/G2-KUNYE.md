# G2 — Araçların künyesi

**Tarih:** 9 Eylül 2026 · **Durum:** bitti

## Bulgu

Yedi araç da yalnız `name` ve `description` ile tanımlıydı. Kütüphanenin
(mcp 2.1.1) kabul ettiği `title`, `annotations`, `icons`, `meta`,
`structured_output` alanlarının hiçbiri kullanılmıyordu.

Bunun iki ayrı bedeli vardı:

- **İstemci tarafı.** `peek` bu sürecin kendi yazdığı bir dosyayı okur; `run`
  kendisine verilen ne komut varsa çalıştırır. İkisi de metin döndürür ve
  dışarıdan birbirine benzer. Otomatik onay veren bir istemci ikisini ayırt
  edemiyordu.
- **Dizin tarafı.** Glama bu ipuçlarını indeksliyor — *"the MCP annotation
  hints that tell you whether a tool is safe to run in automated agent
  loops"*. Anthropic'in araç yazma kılavuzu da adıyla anıyor.

## Doldurulan künye

| araç | read_only | destructive | idempotent | open_world |
|---|---|---|---|---|
| `run` | hayır | **evet** | hayır | evet |
| `follow` | hayır | **evet** | hayır | evet |
| `tool` | hayır | **evet** | hayır | evet |
| `outline`, `digest`, `digest_many` | evet | hayır | evet | evet |
| `peek` | evet | hayır | evet | **hayır** |

Üç kararın gerekçesi var, çünkü üçü de "daha iyi görünen" seçeneği reddediyor:

**`run` yıkıcı.** Kendisine verilen komutu çalıştırır. Başka türlü işaretlemek
bir şey satmak olurdu.

**`tool` yıkıcı.** İlk bakışta `sg`/`diff`/`loc` üçü de okur. Ama
`command_for` argümanları olduğu gibi geçiriyor, ve `ast-grep`'in `--rewrite`
bayrağı dosyayı değiştirir. "Salt okunur" tutamayacağımız bir söz.

**`follow` yıkıcı.** `stop=True` ile bir koşuyu ve başlattığı her şeyi
bitirir. Künye araç başına, argüman başına değil — dolayısıyla en yıkıcı
argümanına göre.

**`open_world` yedide altı evet**, çünkü altısı bir modele soru gönderiyor.
`peek` göndermiyor: yerel dosyayı okur, kimseye sormaz. Tek "hayır" o, ve
bunu söyleyebilmesi künyenin bütün anlamı.

Ayrıca yedi araca insan okuyabilir `title` düştü: `digest_many` bir
tanımlayıcı, *"Digest several files"* bir etiket.

## Testler

Üçü de künyeyi **gerçek taşıyıcıdan** okuyor (kütüphaneyi değil, ağdan geleni):

- `test_every_tool_says_what_it_does_to_the_machine` — beklenen künye tabloya
  yazıldı; kodun kendisinden okunmadı, çünkü test ettiği şeyden cevabı alan
  test hiçbir şey kanıtlamaz
- `test_only_peek_claims_to_stay_on_this_machine` — teeth: `open_world`
  gerçekten ayırt ediyor mu
- `test_every_tool_has_a_name_a_person_can_read`

Bataryaya iki kural: `run`'ın salt-okunur işaretlenmesi ve `peek`'in yerel
iddiasını kaybetmesi. İkisi de yakalandı.
