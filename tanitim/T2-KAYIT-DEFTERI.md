# T2 — Resmî MCP kayıt defteri

**Tarih:** 9 Eylül 2026
**Durum:** bitti — `io.github.slymnysr/sift`, sürüm 1.0.2, `active`

## Neden en önemli kanal

sift bir günlük. Hiçbir modelin eğitim verisinde yok ve olamaz. Ama kayıt
defteri **canlı sorgulanıyor** — istemciler oradan okuyor. Bir modelin sift'i
"bilmesinin" gerçekçi tek yolu bu.

## Yolda çıkan gerçek sorun

Plan T2'yi "server.json yaz, yayınla" diye tarif ediyordu. Yazarken şu çıktı:

Kayıt defteri girdisinin adlandırabildiği tek şey **pakettir**. Bir istemci
girdiden komutu `<runtimeHint> <runtimeArguments> <identifier> <packageArguments>`
sırasıyla kuruyor (kayıt defterinin kendi Snyk örneği bu). Bizim `identifier`
zorunlu olarak `sift-cli`, çünkü sahiplik doğrulaması PyPI'da o adı arıyor.
Ve bugün:

```
$ uvx sift-cli
An executable named `sift-cli` is not provided by package `sift-cli`.
The following executables are available:
- sift
- sift-mcp
```

Yani girdiyi olduğu gibi yayınlasaydık, **bulan herkes çalışmayan bir komut
bulacaktı.** Kayıt defterinde yer almanın amacı bulunmak; bulunup çalışmamak
hiç bulunmamaktan kötü.

Kayıt defterinde 627 PyPI paketine baktım: beşi dışında hiçbiri `--from`
kullanmıyor. Ekosistemin varsayımı açık — **konsol komutunun adı paketin
adıdır.** Bizde değildi, çünkü `sift` PyPI'da alınmıştı.

### Çözüm: 1.0.2

İki ekleme, ikisi de adının söylediği şeyi yapıyor:

| eklenen | ne |
|---|---|
| `sift-cli` konsol komutu | Komut satırının kendisi, ikinci bir adla. `uvx sift-cli` artık kullanım metnini basıyor |
| `sift mcp` alt komutu | `sift-mcp`'nin başlattığı sunucunun aynısı |

Reddedilen alternatif: `sift-cli` komutunu **sunucuya** bağlamak. Tek satır
daha ucuzdu ve yanlıştı — terminalde `sift-cli` yazan biri asılı kalan bir
stdio sunucusu bulurdu. Bu projede adlar söylediği şeyi yapar.

`import`, alt komutun **içinde** duruyor. Eklentisiz `uvx sift-cli mcp` yazan
biri yığın izi değil, cümleyi görüyor — yani `--from` kısmını düşüren bir
istemci bile insanı bir yere vardırıyor.

## Yayın: elle değil, CI

`.github/workflows/registry.yml`, `github-oidc` ile giriyor. GitHub kısa ömürlü
bir belirteç imzalayıp deponun kim olduğunu söylüyor; saklanacak, sızacak,
döndürülecek bir gizli anahtar yok. PyPI'daki güvenilir yayınlamanın aynısı.

İki şeyi varsaymıyor, bekliyor:

- **Sürüm PyPI'da görünene kadar** (60 × 10 sn). Kayıt defteri sahipliği
  PyPI'daki açıklamadan doğruluyor, ve `release` iş akışı bu başlarken hâlâ
  sürüyor olabilir
- **Etiketle `server.json` aynı sürümü söyleyene kadar** — yoksa durur

Sürüm artık dört yerde yazılı (`pyproject.toml`, `__init__.py`, `server.json`
×2). Testler dördünü bir arada tutuyor: unutulmuş bir `server.json` eski bir
girdi yayınlamaz, **hiç** yayınlamaz, ve bunu yayından dakikalar sonra CI'da
öğrenmek pahalıdır.

## Doğrulama — girdinin kendisinden

Girdiyi kayıt defterinden çekip, bir istemcinin kuracağı gibi komutu kurup
gerçekten bağlandım:

```
kurulan komut: uvx --from sift-cli[mcp] sift-cli mcp
araclar: ['digest', 'digest_many', 'follow', 'outline', 'peek', 'run', 'tool']
```

Yedi araç. PyPI'dan indirilen paketle, deponun içinden değil.

## Kayıttaki hâli

| alan | değer |
|---|---|
| ad | `io.github.slymnysr/sift` |
| sürüm | 1.0.2 |
| durum | `active`, `isLatest: true` |
| paket | pypi `sift-cli` 1.0.2, taşıma `stdio` |
| yayın | 2026-09-09T01:05:42Z |
