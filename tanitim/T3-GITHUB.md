# T3 — GitHub keşfedilebilirliği

**Tarih:** 9 Eylül 2026
**Durum:** bitti

Beş dakikalık iş, ve GitHub'ın kendi aramasında sift'in görünüp görünmemesinin
tamamı. Bir depo topics'siz de yaşar; sadece kimse rastlamaz.

## Yapılan

**Açıklama** — arama terimlerini içeriyor, abartmadan:

> MCP server and CLI that runs your command, keeps every byte on disk, and gives
> the model only the lines that matter.

Öncesi "Runs your command, then gives the model only the lines that matter."
idi: doğru, ama içinde ne *MCP server* ne *CLI* geçiyordu — yani insanların
aradığı iki kelime de yoktu.

**Topics (12):**

```
mcp  mcp-server  model-context-protocol  claude  claude-code  llm
context-management  token-optimization  cli  python  ai-agents  developer-tools
```

`model-context-protocol` listeye sonradan eklendi: `mcp` kısaltmasının kendisi
kadar aranıyor.

**Website alanı:** `https://pypi.org/project/sift-cli/` — deponun sağ
üstündeki bağlantı artık kurulum sayfasına gidiyor.

**Releases.** Üç etiket vardı, sıfır release sayfası. Üçü de yazıldı:

| sürüm | başlık |
|---|---|
| v1.0.0 | first release |
| v1.0.1 | a command that works where you are |
| v1.0.2 | in the MCP registry (Latest) |

Release notu, etiketin yapamadığı işi yapıyor: **ne değişti ve neden**. 1.0.2'nin
notu, girdinin komutunu neden yayından *önce* düzelttiğimizi anlatıyor — bulunup
çalışmayan bir girdi hiç bulunmamaktan kötüdür.

## Bitti sayılır

`gh repo view` topics'i döndürüyor, Releases sayfası dolu, açıklamada aranan
kelimeler var.
