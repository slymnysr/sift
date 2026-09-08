# 23 — Ölçüm birimi: rapor neyi sayar, neyi saymayı reddeder

**Nereden çıktı:** Headroom karşılaştırması. Onlar dolar basıyor ve ölçemediğini
güven aralığıyla veriyor. Buradaki `stats` bayt basıyordu.

## Sorun

`stats`, kurulan kişinin gerçekten sorduğu soruyu cevaplıyor: *harcadığı isteğe
değiyor mu?* Bunu baytla cevaplayamaz. Bayt ne bir isteğin faturalandığı şey, ne
de bir bağlam penceresinin tuttuğu şey.

## Tahmin değil ölçüm

Kolay yol vardı ve alınmadı: baytı dörde böl. Bu, İngilizce düzyazı hakkında bir
kestirme kuraldır ve bir sayı kılığında satılır. Bu araç Japoncaya, Türkçeye,
base64'e ve yığın izlerine doğrultuluyor — oralarda yanlışlık bir pay değil, bir
kat meselesi.

Uç nokta OpenAI şeklinde cevap veriyor ve cevabında `usage` var. Yani sayı zaten
ölçülmüş durumda; yapılacak tek şey onu **okumak**. `_spent` bunu yapıyor ve
başka hiçbir şey yapmıyor.

## Asıl teslim: reddetme

Bu fazın kodundan çok, kodun **yapmadığı** şey önemli.

Cevap `usage` söylemediyse sonuç **sıfır**. Sıfır burada "bedava" demek değil,
**"kimse saymadı"** demek. Ve o boşluk aritmetikle doldurulmuyor:

| Durum | Ne yazılır |
|---|---|
| Uç nokta saydı | Onun sayısı |
| Uç nokta saymadı | `—`, ve toplamda "1 not counted" |
| Model hiç erişilemedi (yedek) | 0 |
| Cevap hatırlandı (22. faz) | 0 |

Son iki satır ölçümün kendisi: yedek gerçekten bedava, hatırlanan cevap gerçekten
istek harcamıyor. 22. fazın kazancı burada görünür hâle geliyor.

Toplam satırı da hangi sayının ne olduğunu söylüyor:

```
12 runs · 1,234,567 B captured · 45,678 B shown · 3.7% of it · ...
cost 12,345 tokens, as the endpoint counted them, 2 not counted
```

Üstteki pay bu aracın kendi baytları üzerindeki aritmetiği — **kesin**. Alttaki
maliyet uç noktanın kendi sayısı — **ölçülmüş**. İkisi karıştırılmıyor.

## İkinci pas da bir istek

`narrow` ikinci (ve üçüncü) turu ayrı istekler olarak yapıyor. Yalnız ilkini
sayan bir rapor, aracı **en çok çalıştığı anda** olduğundan ucuz gösterirdi.
Bunun mutasyonu ve testi var.

## Dipnota dokunulmadı

Maliyet rapora ait, her görünüme değil. Dipnotu okuyan kişi kendi çıktısına
bakıyor; bir isteğin ne tuttuğu onun baktığı şey değil. Testi de var, çünkü
"eklemedim" bir süre sonra "unuttum"a benziyor.

## Ölçü

- Önce: `stats` yalnız bayt basıyordu; harcanan istek sayısı vardı, maliyeti yoktu.
- Sonra: her görünüm uç noktanın saydığı token'ı taşıyor, `stats` onu basıyor,
  sayılmayanı sayılmış gibi göstermiyor.
- Bu fazın dört kuralı da mutasyon bataryasında.
