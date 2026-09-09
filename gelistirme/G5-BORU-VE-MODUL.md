# G5 — Boru ve modül

**Tarih:** 9 Eylül 2026 · **Durum:** bitti

İki küçük eksik, ikisi de "beklenen yol" olduğu için eksikliği ancak çarpınca
görülüyor.

## `python -m sift`

`src/sift/__main__.py` yoktu. Konsol komutu, onu bir yere koyan bir kurulum
ister; modül yalnız paketi ister. Aktive edilmiş bir sanal ortam, bir CI işi,
bir kopyaya bakan `PYTHONPATH` — dördü de çalışabilmeli.

Bu eksiğe bu projede bir kez çarpıldı: `test/kazanc.py` yazılırken. Çözüm o gün
konsol komutunu aramak olmuştu.

## `sift digest -`

Bir boru, başkasının çıktısının bu araca ulaşmasının **öteki** yolu.
`sift run` bu sürecin sebep olduğu çıktı içindir; boru ise zaten yolda olan
çıktı: `journalctl | sift digest -`, bir meslektaşın gönderdiği kayıt, sift'in
dışında koşan bir derleme.

### Karar: geçici dosya değil, kayıt

Kolay yol geçici bir dosyaya yazmaktı. Yapılmadı, çünkü **ikinci kural**:
görünümün dışarıda bıraktığı her satır `peek`'in ulaşabileceği bir yerde
kalmalı. Çıkışta silinen bir dosyaya işaret eden bir boşluk işareti, daha
okunmadan bozulmuş bir sözdür.

Onun yerine gelen bayt bir **kayıt** oluyor — `sift run`'ın yaptığının aynısı —
ve boşluk işareti tutamacı adlandırıyor:

```
$ journalctl -u nginx | sift digest -
Sep 08 04:11:07 nginx[2114]: worker process 2119 exited on signal 11
─ 8,204 lines not shown · sift peek 7c1a04e9 for any of them ─
```

`-` bir yol değil, bir sözleşme. Bu yüzden görünümün adı ile okunan dosya artık
iki ayrı şey: `digest`, `outline` ve `view` yardımcıları bir `name` alıyor.
Öntanımlı hâli eskisi gibi yolun kendisi.

Çalıştırılmayan bir şeyin çıkış kodu da yok: `exit_code=None`. Uydurulmadı.

## Bataryanın ikinci kez yakaladığı şey

`capture.keep` akışı bloklar hâlinde okuyor. İlk testlerim 200 satırlıktı — tek
blok. Yani şu mutasyon **kaçtı**:

```python
while True: ... sink.write(block)   →   sink.write(source.read(_READ_CHUNK))
```

64 KB'ın ilkini okuyup durmak, dört satırlık testlerin hepsinden geçiyordu. Oysa
boruya uzanmanın sebebi tam da yapıştırılamayacak kadar büyük bir kayıt.

Şimdi bir test 20.000 satır boruluyor ve `peek`'in harfi harfine aynısını geri
verdiğini iddia ediyor. Mutasyon artık yakalanıyor.

G4'te de aynı şey olmuştu. İki fazda iki kez: **testin kendisi de ölçülmeli.**
