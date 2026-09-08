# Faz 17 — Yoğun araçlar

## Fazın cümlesi

Üç program, ve hepsinin ortak özelliği: **okumanın yerine geçiyorlar.**

| ad | program | neyin yerine geçiyor |
|---|---|---|
| `sg` | ast-grep | bir şeklin nerede geçtiğini bulmak için dosyaları tek tek açmak |
| `diff` | difftastic | girinti değişikliğini değişiklik sanan satır bazlı diff |
| `loc` | scc | bir ağacın ne kadar büyük olduğunu tahmin etmek ya da listeleyerek öğrenmek |

Bunlar sift'e ait çünkü çıktıları doğaları gereği büyük: 4.000 satırlık yapısal
bir arama burada bir ekran maliyetinde ve tamamı diskte duruyor.

## Hiçbir ikili paketle gelmiyor

Buradaki liste, bir makinede olabilecek ya da olmayabilecek programların
listesidir — bir bağımlılık değil. Hiçbir şey indirilmiyor, hiçbir şey arkadan
kurulmuyor. Bir araç yoksa `sift tools` bunu ve adını söylüyor; kararı makinenin
sahibi veriyor.

## Liste kısa ve kısa kalmalı

Üç madde, bir dil tablosunun kılık değiştirmiş hâli değil: aynı üçü, proje hangi
dilde yazılırsa yazılsın aynı üçü. Dördüncüsü ancak **o da okumanın yerine
geçiyorsa** girebilir.

Bu, `outline`'ın 1.099 satırlık dil tablosunu 95 satıra indiren kararla aynı
kural: sayılan bir liste bakım ister ve eskir. Bu liste sayılıdır, dolayısıyla
sınırı da açıkça yazılmıştır.

## Bu fazın dersi

**Bir listenin meşru olup olmadığını uzunluğu değil, neyi saydığı belirler.**

Dilleri saymak yanlıştı: sonsuz bir kümeyi sonlu bir tabloyla temsil ediyordu.
Üç programı saymak doğru: küme gerçekten üç elemanlı ve büyümesi de bir kurala
bağlı.
