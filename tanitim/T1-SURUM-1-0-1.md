# T1 — Sürüm 1.0.1

**Tarih:** 9 Eylül 2026
**Durum:** bitti

## Neden bir sürüm daha

İki ayrı iş aynı yayına bindi.

**Birincisi kayıt defteri.** `registry.modelcontextprotocol.io`, PyPI
sahipliğini paketin **açıklamasından** doğruluyor: yayınlanmış sürümün
`long_description`'ında `mcp-name: io.github.slymnysr/sift` dizesi geçmek
zorunda. 1.0.0'da geçmiyordu. README GitHub'da anında değişir ama PyPI'daki
açıklama sürümün içinde donmuştur — yani T2 yeni bir sürüm olmadan yapılamazdı.

**İkincisi 28. fazdan kalan borç.** `sift-mcp`, `mcp` eklentisi olmadan
çalıştırıldığında kullanıcıya `pip install "sift-cli[mcp]"` diyordu. O komut
Debian, Ubuntu ve WSL'de PEP 668 gereği reddediliyor. README düzeltilmişti;
mesaj paketin içinde ships ettiği için kodda bekliyordu.

## Yapılan

| dosya | değişiklik |
|---|---|
| `README.md` | Başlığın altına `<!-- mcp-name: io.github.slymnysr/sift -->` |
| `src/sift/server.py` | `pip install` → `uv tool install`, altına `pip`in neden reddedildiği |
| `test/test_server.py` | Aynı dizgeyi arayan iddia; ayrıca "çalışmayan komut verilmemeli" kontrolü |
| `test/mutations.py` | Aynı dizgeyi çapa olarak kullanan mutasyon |
| `pyproject.toml`, `src/sift/__init__.py` | 1.0.0 → 1.0.1 |

Beşi de aynı cümleye bağlıydı; `test_package.py` zaten sürümün iki yerde
uyuşmasını istiyor, o yüzden `__init__.py`'yi unutmak testte anında yakalandı.

## İşaret gerçekten pakete girdi mi

Yorum satırı olduğu için gözle görünmüyor; bu yüzden yayından önce paketin
kendisinden okundu:

```
sdist  PKG-INFO  Description-Content-Type: text/markdown
sdist  isaret var mi: True        version: 1.0.1
wheel  isaret var mi: True        version: 1.0.1
```

PyPI açıklaması bu `Description` alanından üretiliyor. crates.io HTML yorumlarını
siliyor, PyPI korumuyor — bizde sorun yok.

## Bitti sayılır

Plandaki ölçüt: *PyPI'daki 1.0.1 açıklamasında `mcp-name` dizesi görünüyor.*
