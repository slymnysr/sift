# 20 — Kayıt birimi: satırın birim olmadığı yer

**Nereden çıktı:** Headroom karşılaştırması (bkz. `00-PLAN.md`). Onların JSON
sıkıştırıcısından alınan şey sıkıştırma değil, **birim fikri**.

## Delik

Bu araçtaki her şey satır sayıyordu ve komut çıktısı için bu doğru: satır,
yazanın "bir şey" olarak kastettiği ve okuyanın gözünün takıldığı birimdir.

JSON dizisi bunun düpedüz yanlış olduğu yer. Makine tarafından makine için
yazıldığında çoğu zaman hiç satır sonu yoktur — 1. satırda 400 KB — ve o zaman
seçilecek tam **bir** birim vardır, onu seçmek de hepsini göstermek demektir.
Girintili yazıldığında daha sessiz bir biçimde kötüdür: satırlar vardır ama bir
tanesi `"id": 3,`'tür — doğru, seçilmiş, dosyadan bayt bayt alınmış ve hiçbir
işe yaramaz.

İkisi de daha iyi bir soruyla düzelmez. **Birim yanlıştır.**

Ölçü: 4 kayıtlık tek satırlık bir dizide `lines.of` **1** birim buluyor,
`records.of` **4** buluyor. Testteki örnek 262 bayt; asıl vakada bu 400 KB.

## Ne değişti, ne değişmedi

Değişen tek şey **neyin sayıldığı**. Model yine yalnız numara döndürüyor, metin
yine kaynaktan bayt bayt basılıyor, boşluk yine kaçının katlandığını söylüyor.

Değişmeyenin kanıtı testte:

```python
found[0] == '{"z":1, "a":2, "big":1E2, "round":1.0}'
found[0] != json.dumps(json.loads(found[0]))
```

Bir kayıt, kaynağın `text[at:end]` dilimidir. Ayrıştırılmış değeri geri yazmak
—`json.dumps`— bu aracın metin yazması olurdu ve **sessizce** yanlış olurdu:
`1E2` geri `100.0` olarak gelir, `1.0` bazen `1.0` kalır, anahtar sırası
kimsenin koymadığı bir bayrağa bakar. Çoğu zaman çalışıyormuş gibi görünürdü.

Tarama, köşeli parantez sayan bir döngüyle değil, standart çözücüyle yapılıyor.
Sebebi köşe durumu değil, sıradan durum: bir kaydın içindeki log satırı.

```json
[{"msg": "expected ] at end of [list], got }"}, {"msg": "fine"}]
```

Sayan her döngü bunu aynı yerde yanlış böler.

## Kapsam kararı: yalnız üst düzey dizi

`{"results": [...]}` gibi bir nesne satır olarak bırakılıyor. Bu bir eksiklik
değil, karar: bir nesnenin hangi dizisinin "kayıtlar" olduğunu seçmek, başkasının
şeması hakkında **tahmin** yürütmektir — ve okuyanın ne göreceğine karar veren
bir tahmin, bu projenin baştan yazılma sebebidir (5. faz). Daha iyisini bilen
çağıranın elinde `--keep` var.

Aynı gerekçeyle reddedilenler: dizinin ardından devam eden metin (o zaman
"katlanan kayıt sayısı" bütünün sayısı olmaz), kapanmamış dizi, boş dizi ve tek
kayıt. Sonuncusu için sebep ayrı: **bir kayıt bir seçim değildir**, ve onun
görünümü zaten metnin kendisidir.

`records.of` bunların hepsine hata fırlatarak değil `None` diyerek cevap veriyor.
Bu her yakalamaya soruluyor ve neredeyse hiçbiri JSON değil; "hayır" burada
olağan cevap, arıza değil, ve ilk karaktere bakarak veriliyor.

## Sayının adı

Birim `View` üzerinde taşınıyor, dipnotu basan yer yeniden hesaplamıyor. Sebep:
bir kaydı sayarken "satır" diyen bir dipnot bir yazım hatası değil — bu projenin
kendisi hakkında yayınladığı tek sayıyı, olmadığı bir şey olarak tarif etmesidir.

Boşluk işareti de birimle değişiyor, ama `peek` satırla adreslendiği için cümle
farklı: kayıt için "sift peek `<handle>` for the text they came from". İkinci
kural her birime bir adres vaat etmiyor; **hiçbir şeyin atılmadığını** vaat
ediyor, ve o duruyor.

## Ders

Bir aracın "her yerde çalışır" iddiası, birimini sabit tuttuğu sürece sahtedir.
Model tarafını dilden bağımsız yapmak (5. faz) yetmiyor: kararın **neyin
üzerinde** verildiği de metne sorulmalı. Burada sorulan soru "bu ne tür bir
dosya" değil — o bir liste olurdu — "bu metin bir dizi mi", ve cevabı baytların
kendisi veriyor.
