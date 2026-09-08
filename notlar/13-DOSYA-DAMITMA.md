# Faz 13 — Dosya damıtma

## Fazın cümlesi

Elinde olan ama açamadığın bir dosya: dün gece CI'ın yazdığı build log'u, bir
issue'ya eklenmiş test raporu, bir crash dump, 40.000 satırlık bir JSON export.
Çalıştırılamaz, kaynak kod değil. Üçüncü soru bunun için var.

## Aynı motor, üçüncü soru

| komut | soru |
|---|---|
| `run` | bu komutta ne oldu? |
| `outline` | bu dosya ne bildiriyor? |
| `digest` | bu dosyada ne var? |

Ayrım dosyada değil **soruda**. Bir log'a "ne bildiriyor" diye sorarsan işe
yaramaz bir cevap alırsın; bir Python modülüne "ne oldu" diye sorarsan
import'larını alırsın. Hangisini elinde tuttuğunu çağıran bilir ve komut kelimesi
tam olarak bunu söylediği yerdir — `run` ve `outline` için de böyleydi.

Sorunun içinde bir uyarı var: *bu dosya yazılırken yarıda kesilmiş olabilir, son
satırların sonuç olduğunu varsayma.* Komut çıktısında bu varsayım güvenliydi
(komut bitmişti); kaydedilmiş bir dosyada değil.

## Değişmeyen

Dosya burada açılıyor, içeriği konuşmaya hiç girmiyor. Model yalnız numara
döndürüyor. Gösterilen her satır dosyanın kendi baytları. 40.000 satırlık bir log
bir ekran maliyetinde, kalan 39.900 satır bir `sift peek` uzakta — çünkü dosyaya
dokunulmadı.

## Bu fazın dersi

**Bir motorun üçüncü kullanıcısı, motorun doğru soyutlandığının kanıtıdır.**

`select` üç farklı soruya, üç farklı kaynağa (komut, kaynak dosya, kayıt dosyası)
tek satır değişmeden cevap verdi. Bir soyutlama ikinci kullanıcıda tesadüfen
tutabilir; üçüncüde tutuyorsa doğru yerden ayrılmıştır.
