# G8 — Kazancı araç söylesin

**Tarih:** 9 Eylül 2026 · **Durum:** bitti

## Bulgu

`stats` şunu basıyordu: yakalanan bayt, gösterilen bayt, oran, kaç istek,
**harcanan** token. Kurulan kişinin sorduğu soru ise şu: *bu istek etmeye
değdi mi?* Cevabın paydası eksikti — çıktının kendisi kaç token'dı?

Araç bu sayıyı zaten alıyordu ve atıyordu. Her soruda uç nokta `usage` döndürüyor;
`_spent` yalnız `total_tokens`'ı okuyup `prompt_tokens`'ı görmezden geliyordu.

## Eklenen: `weighed`

`prompt_tokens` = uç noktanın, kendisine verilen her şeyden anladığı. Yani
**çıktının kendisi**, numaralanmış hâliyle, önünde soruyla.

```
handle    captured    shown  part  asks  weighed    cost  command
9f2c41ab  62,003 B    450 B  0.7%     1   21,392   5,120  pytest -v

cost 5,120 tokens, as the endpoint counted them
the output put to a model weighed 21,392 tokens -- numbering and question included
```

İki karar bu sayıyı dürüst tutuyor:

**Fazlalığı söylemek, çıkarmamak.** Sayı, yakalamanın kendisinden biraz
fazladır — numaralandırma ve soru da içinde. Bunu tahminle çıkarmak, ölçümü
tahmine çevirmek olurdu. O yüzden basıldığı yerde yazıyor: *"numbering and
question included"*.

**Daraltmayı saymamak.** `narrow`, aynı yakalamadan çıkarılmış bir kısa listeyi
yeniden soruyor. Onun `prompt_tokens`'ını da eklemek bazı satırları iki kez
sayardı — ve okuyucunun böleceği sayıyı şişirirdi. İlk geçiş yakalamayı taşıyor;
ondan sonrası taşımıyor. Bir test bunu tutuyor.

**Görünümün kendi ağırlığı sayılmıyor.** Onu ölçmek istek harcar; ölçen şey
`test/kazanc.py` ve zaten var. `stats` bedavaya bildiğini basıyor, bilmediğini
uydurmuyor.

## 23. fazın reddi aynen duruyor

Sayılmamış koşu sayılmamış kalıyor: `—` basılıyor ve toplamdan çıkarılıp
"1 not counted" deniyor. Eski `view.json` dosyaları alanı taşımadığı için
kendiliğinden bu durumda görünüyor — ki doğrusu bu, o koşuları kimse tartmadı.

## Rapor artık aleyhte de konuşabiliyor

Gerçek bir koşuda ölçülen:

```
1 run · 3,158 B captured · 253 B shown · 8.0% of it
cost 2,238 tokens
the output put to a model weighed 1,917 tokens
```

Küçük bir çıktıda **sorunun maliyeti, çıktının ağırlığını aşıyor.** Bu bir hata
değil, raporun işini yapması: sift küçük çıktılarda kâr etmez, büyüklerinde
eder, ve artık hangisinde olduğunu okuyabiliyorsun.

## Bataryaya üç kural

| kural | kırıldığında |
|---|---|
| Ağırlık cevaptan okunur, tahmin edilmez | `_carried` sıfır döner |
| Daraltma yakalamayı ikinci kez saymaz | Sayı şişer |
| Tartılmamış koşu tire basar, sıfır değil | Kimse ölçmemiş bir koşu ölçülmüş görünür |

Üçü de yakalandı.
