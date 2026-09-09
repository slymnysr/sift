# T6 — README konumlandırma

**Tarih:** 9 Eylül 2026
**Durum:** bitti

## Sorun

README şöyle başlıyordu:

> Runs your command, then gives the model only the lines that matter.

Doğru bir cümle, ve **kimsenin aradığı bir cümle değil.** İçinde ne *MCP*, ne
*context*, ne *token* geçiyor. İnsanların aradığı: *MCP token waste*, *tool
output floods context*, *reduce Claude context usage*, *agent context window
full*.

## Yapılan — üç dokunuş, hepsi ilk ekranda

**1. "conversation" → "context window".** Aynı şey, ama biri aranan kelime.

**2. Araç kendini adlandırıyor.** "`sift` is an MCP server and a command line
for that problem." Öncesinde README'nin ilk ekranında "MCP" kelimesi hiç
geçmiyordu.

**3. İki ölçülmüş sayı.** Pazarlama cümlesi değil, iki tablo satırı:

| ne | ölçüm |
|---|---|
| Ne kadarı gitti | Bu projenin kendi test koşusu 652 satır / 21.392 token; geri gelen 8 satır / 208 token — **%99 daha az** |
| Ne kadarı kaldı | 22 örneklik korpusta varsayılan bütçe, okunması **şart olan 140 satırın 138'ini** tutuyor |

İkisi birlikte duruyor, çünkü tek başına birincisi hiçbir şey söylemez: her
şeyi atmak kolaydır. Pahalı olan ikincisidir.

Her ikisi de depodan yeniden üretilebilir: `python test/kazanc.py` ve
`python test/budget.py`.

## Ölçüm nasıl yapıldı — ve yakalanan hata

`test/kazanc.py` bu faz için yazıldı. Üç istek atıyor: biri boş (her mesajın
taşıdığı sabit yükü ölçmek için), ikisi metinler için, ve `usage.prompt_tokens`
okuyor. **Bayt dörde bölünmüyor** — bu araç Japoncaya, base64'e ve yığın
izlerine doğrultuluyor; orada o kestirme kural bir pay değil kat hatası verir.
Ölçülen şey, bir çağıranın gerçekten aldığı metin: görünüm **artı** altbilgi,
çünkü MCP üzerinde altbilgi sonucun içinde gidiyor.

**Ve bu faz bir hata yakaladı.** `tanitim/00-PLAN.md`'nin T6 bölümü, elimizde
"404 satır → 7 satır, %97,6 daha az token" ölçümü olduğunu yazıyordu. Öyle bir
ölçüm yok: `%97,6`, `notlar/26`'da **efor kıyasının kalite oranı**. Yani bu
planın kendi son kuralını — *"olmayan bir şeyi iddia etmek hem yanlış hem de bu
projenin bütün duruşuna aykırı"* — plan yazarken ihlal etmişim.

Sayı gerçekten ölçüldü, plan düzeltildi, ve **yanlış sayıyla dışarı çıkmış iki
yer geri dönülüp düzeltildi**: mcp.so gönderimi (issue #4010) ve
awesome-mcp-servers PR'ı (#14050). Bir dizinde duran yanlış sayı, README'de
duran yanlış sayıdan beterdir: kimse orayı bir daha okumaz.

## Bitti sayılır

README'nin ilk ekranı problemi arama terimleriyle adlandırıyor ve iki ölçülmüş
sayı gösteriyor.
