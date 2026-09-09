# G10 — Bataryayı uçtan uca

**Tarih:** 9 Eylül 2026 · **Durum:** bitti
**Koşu:** 19:58 → 22:08, 195 kural, tek başına

## Sonuç

```
173/195 caught
```

Kalan 22'si **iki ayrı hastalıktı** ve ikisi de düzeltildi. Ham çıktı
`G10-batarya.log`, düzeltme sonrası doğrulama `G10-yeniden-kosum.log`.

## Ölü kurallar: 16 tane, ve bunlar kaçandan beter

`NO ANCHOR` — mutasyonun aradığı metin kodda artık yok. Kaçan bir mutasyon
*"bu kural korumasız"* der; çapası düşmüş bir mutasyon **hiçbir şey demez**:
listede durur, sayıya girer, ve korunuyormuş gibi görünür. 16 kural aylardır ya
da saatlerdir sessizce hiçbir şey koruyormuş.

Sebepleri üç grupta toplandı:

**Bugünkü işlerimin kırdıkları.** G6 `sink.write` → `kept.write` yapınca G5'in
akış kuralının çapası düştü — üstelik o kuralı G5'te *yakalandı* diye
doğrulamıştım. G1 ikinci bir `return written or None` getirince efor kuralı
belirsizleşti (2 eşleşme). G5 ikinci bir `store.finish(meta)` getirince
tamamlanma kuralı iki yere birden uydu.

**Aylardır ölü olanlar.** 26. faz amiral modeli merdivenden çıkarmış; "en büyük
model önce sorulur" kuralı hâlâ `nemotron-3-ultra` arıyordu. Kural artık öyle
bir kural değil — **yeniden yazıldı**: *"merdiven yazıldığı sırayla sorulur"*.

**Sürüm çapası.** `__version__ = "1.0.0"` arıyordu; paket 1.0.2'deydi. Üç yayın
boyunca ölü. Artık üzerinde bir not var: bu çapa her yayınla birlikte taşınır,
ve unutulursa batarya `NO ANCHOR` diyerek söyler — nitekim söyledi.

## Korumasız kurallar: 6 tane

`ESCAPED` — mutasyon uygulandı, suite hiçbir şey demedi. Yani o kural
gerçekten korumasızdı.

| kural | testlerin göremediği |
|---|---|
| Follow numaraları yakalamanın kendisinin | Her test yalnız **ilk** bakışa bakıyordu, ve `first=1`'de "yakalamanın numarası" ile "birden say" aynı cevabı veriyor |
| Maskede çevre metin sağ kalır | Herkes sırrın gittiğini kontrol ediyordu; geri kalanın durduğunu kimse |
| Geçersiz desen düz metin aranır (distill) | **Desen geçerliymiş** — `main()` derlenir, parantezler boş gruptur |
| `--keep` seçime ulaşır | Modelsiz koşuda `keep` hiçbir şeye karar vermiyor; ayırt etmek için yargıç gerekiyor |
| Tek geçit uçan soru sayısını sınırlar | Hiçbir test aynı anda kaç sorunun uçtuğunu saymıyordu |
| Aynı komutun koşuları birlikte sayılır | Test komutun *göründüğünü* kontrol ediyordu, **sayısını** değil |

Yedi test yazıldı (bir kural iki dosyada geçiyor).

### Ve yazdığım testin kendisi de kaçırdı

Maskeleme testinin ilk hâli şöyleydi:

```python
line = f"GET /users?page=2 Authorization: Bearer {SECRET} -> 401 in 12ms"
assert "GET /users?page=2" in masked
assert "-> 401 in 12ms" in masked
```

Mutasyon yine kaçtı. Sebep: `re.sub` yalnız **eşleşeni** değiştirir, ve benim
işaretlerim eşleşmenin *dışındaydı* — mutasyonla da hayatta kalıyorlardı. Doğru
işaret eşleşmenin içinde olmalıydı: `Bearer` kelimesi, ya da bağlantı
dizesindeki `postgres://reader:` ve `@db.internal`.

Yani batarya bu projede **dördüncü** kez bir testin hiçbir şey kanıtlamadığını
gösterdi, ve bu sefer test aynı gün, bunun için yazılmıştı.

## Makine iki kez öldürdü, journal iki kez kurtardı

Düzeltme sonrası doğrulama koşumu arka planda iki kez **bellek muhafızı
tarafından öldürüldü**. `SIGKILL` `finally`'yi çalıştırmaz, yani ikisinde de
diskte **bozuk bir kaynak dosya kaldı** (`capture.py`, sonra `model.py`).

19. fazın journal'ı tam bunun için var ve iki kez de işe yaradı:
`undo_leftover()` dosyayı geri koydu, suite yeşile döndü. Bu, o fazın
gerekçesinin ölçülmüş üçüncü kanıtı.

Çözüm: doğrulama beşerli partiler hâlinde **ön planda** koşuldu. Uzun yaşayan
bir arka plan süreci bu makinede hedef oluyor.

## Bitti sayılır

| | |
|---|---|
| Tam koşu | 195 kural, 173 yakalandı |
| Düzeltme sonrası | 22 kuralın 22'si yakalandı |
| Şu an çapasız kural | **0** |
| Şu an korumasız kural | **0** |
| Test sayısı | 688 (bu fazda +9) |

Not, dürüstlük için: ikinci bir **tam** koşu yapılmadı. Düzeltmeler yalnız test
ekledi ve mutasyon çapası tazeledi — kaynak koda dokunulmadı — o yüzden ilk
koşudaki 173 sonuç geçerliliğini koruyor. İkinci tam koşu 2 saat daha demekti ve
makine bu gece iki uzun süreci zaten öldürdü.
