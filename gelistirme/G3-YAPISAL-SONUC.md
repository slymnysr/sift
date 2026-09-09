# G3 — Sonucun içinde veri: ölçüldü, yapılmadı

**Tarih:** 9 Eylül 2026 · **Durum:** reddedildi, gerekçesiyle

## Plan ne diyordu

> Metin **birebir aynı kalır**, yanına alanlar düşer: `handle`, `exit`,
> `shown`, `total`, `model`, `cached`. Ajan çıkış kodunu düzyazıdan çıkarmak
> zorunda kalmasın.

Kulağa bedava geliyor. Değil.

## Ölçüm

MCP'de `structuredContent`, `content`'in **yanına** eklenir. Yani bir sonuç
büyür. Ne kadar büyüdüğü tahmin edilecek bir şey değil, ölçülecek bir şey:

```json
{"handle":"a35f6120","exit":0,"shown":3,"total":652,
 "model":"nvidia/nemotron-3-super-120b-a12b","cached":false}
```

Aynı tokenizer'la (uç noktanın kendi sayacı), gerçek bir `run` sonucu üzerinde:

| | token |
|---|---|
| bugünkü sonuç (görünüm + altbilgi) | 129 |
| yapısal blok eklenmiş hâli | 180 |
| **eklenen** | **51 — %39,5** |

## Karar

**Hayır.** Bağlamı küçültmek için var olan bir aracın, her sonucu %39,5
büyütmesi. Karşılığında alınan şey: ajanın, zaten okuduğu bir altbilgiyi
ayrıştırmak zorunda kalmaması.

Altbilgi ayrıştırılacak bir şey değil, **okunacak** bir şey:

```
sift a35f6120 · exit 0 · 3/652 lines · nvidia/nemotron-3-super-120b-a12b · 66.3s
```

Bir model bunu okur. Aynı olguları bir de JSON olarak göndermek, aynı bilgiyi
ikinci kez ödemektir — ve bu projenin bütün konusu tam olarak odur.

`list` ve `stats`'ın MCP'de sunulmaması, amiral modelin merdivenden
çıkarılması, `stats`'ın kestirme token tahmini yapmayı reddetmesi — hepsi aynı
kararın başka örnekleri. Bu da onlardan biri.

## Bunu değiştirecek şey

Bir istemcinin `structuredContent` varken `content`'i modele **göndermediği**
gösterilirse hesap değişir: o zaman alanlar bedava olur, altbilgi de yerinde
kalmaya devam eder (görüntüleme için). Bugün bunu iddia edecek bir ölçümümüz
yok, ve ölçmediğimiz bir davranışa dayanarak %39,5 ödemeyiz.

Kapı açık; ödeme yapılmadan geçilmiyor.

## Elde kalan

Ölçüm betiği `test/kazanc.py` ile aynı yöntemi kullandı ve tek seferlikti;
sayı buraya yazıldı. Kod tabanında hiçbir şey değişmedi — bu fazın ürünü
**değişmemiş kod ve yazılmış bir gerekçe.**
