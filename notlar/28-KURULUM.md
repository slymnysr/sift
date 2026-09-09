# 28 — Kurulum: bir yabancının izlediği yol

**Nereden çıktı:** Kullanıcı "dışarıdan biriymişim gibi kur" dedi. Ben de
hafızamdaki bilgiyi kullanmadan, yalnız **yayınlanmış belgelere** bakarak
kurdum. Amaç bir rol yapmak değildi; sınanan şey şuydu: *yayınladığımız
belgeler, bir yabancının doğru kurması için yeterli mi?*

Cevap: neredeyse. Bir yerde takılıyordu.

## Bulunan hata: `pip install` bu makinelerde çalışmıyor

README şunu diyordu:

```bash
pip install "sift-cli[mcp]"
```

Debian, Ubuntu ve WSL'de bu komut **başarısız olur**. O sistemler sistem
Python'una bir işaret koyar:

```
/usr/lib/python3.12/EXTERNALLY-MANAGED
```

ve `pip` PEP 668 gereği reddeder:

```
error: externally-managed-environment
× This environment is externally managed
```

Bu ret **doğrudur** — sistem paket yöneticisinin kurduğu Python'a pip ile
yazmak dağıtımı bozar. Yanlış olan, README'nin çalışmayan bir komut vermesiydi.

Ve cevap `--break-system-packages` değil. Bir komut satırı aracı zaten kendi
ortamında olmalı: `uv tool install` ya da `pipx install`. İkisi de `sift` ve
`sift-mcp`'yi PATH'e koyar, hiçbir şeye bulaşmadan.

README düzeltildi.

## Kodda da aynı cümle var — ve bekliyor

`src/sift/server.py`, `mcp` eklentisi olmadan çalıştırılınca şunu basıyor:

```
sift-mcp: the server half needs one more package.

    pip install "sift-cli[mcp]"
```

**Aynı hata, aynı sebep.** Bir Ubuntu kullanıcısı bu mesajı okuyup komutu
çalıştırırsa yine reddedilir — ve bu sefer aracın kendi ağzından yanlış bir
tavsiye almış olur, ki README'den daha kötüdür.

**Neden hemen düzeltilmedi:** README GitHub'da anında güncellenir; koddaki
mesaj **paketin içinde ships**, yani düzeltmek yeni bir PyPI sürümü gerektirir
(`1.0.1`, yeni tag, yeni yayın). Bu yüzden bekleyen iş olarak buraya yazıldı.

**Bir sonraki sürümde yapılacak:**

- `src/sift/server.py` → `NO_MCP` mesajındaki `pip install "sift-cli[mcp]"`
  satırı `uv tool install "sift-cli[mcp]"` olacak, ve altına *"or `pipx`; plain
  `pip` is refused by Debian/Ubuntu/WSL"* notu düşülecek
- `test/test_server.py` → `test_and_the_test_above_would_have_noticed` o dizgeyi
  arıyor, birlikte güncellenecek
- `test/mutations.py` → aynı dizgeyi çapa olarak kullanan mutasyon var

Üçü aynı cümleye bağlı; biri değişirse üçü de değişmeli.

**Yapıldı — 9 Eylül 2026, sürüm 1.0.1** (`tanitim/T1-SURUM-1-0-1.md`).

## Kurulumun geri kalanı çalıştı

| adım | sonuç |
|---|---|
| `uv tool install "sift-cli[mcp]"` | `sift` ve `sift-mcp` PATH'te |
| Anahtar (`~/.config/nvidia/api_key`) | Kendiliğinden bulundu |
| `claude mcp add --scope user sift -- sift-mcp` | `✔ Connected` |
| İstemci gibi konuşma | 7 araç listelendi, 120 satır → 6 satır |

## İki not, ikisi de kullanıcı deneyimi hakkında

**PyPI sayfası okunamıyor.** Bir asistan `pypi.org/project/sift-cli/` adresini
çekmeye çalışınca JavaScript hatası alıyor. İkinci hamle README'nin ham hâli
oluyor ve o çalışıyor. Yani **README, PyPI açıklaması değil, gerçek giriş
kapısı** — orada eksik olan hiçbir yerde telafi edilmiyor.

**Döngüyü asistan kapatamıyor.** İki adım insan gerektiriyor: NVIDIA anahtarını
almak (tarayıcıda kayıt, OAuth akışı yok) ve istemciyi yeniden başlatmak (MCP
sunucuları yalnız oturum açılışında bağlanır). Kurulumun tamamı otomatikleşemez,
ve bu bir kusur değil — ama tanıtımda bunun yazılması gerekir, yoksa "iki
komutla kurulur" diyen her metin yanlış olur.
