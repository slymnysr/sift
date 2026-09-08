# Faz 12 — Çağıranın söz hakkı

## Fazın cümlesi

On bir faz boyunca ne gösterileceğine hep araç karar verdi: model satırı seçer,
tavan bütçeyi belirler, kod garantiyi verir. Bu fazda çağıran da konuşuyor:
`--keep`, `--budget`, `--cwd`.

## Ek fazlar neden var

Bu faz bir boşluğun kapatılmasıyla başlıyor ve o boşluğun sebebi bende.

Hedef şuydu: *"var olan özellikleri **tümüyle** fazlara bakarak AI'ya göre
güncellemeliyiz."* Planı 11 faza bölerken eski projenin (winnow) araç listesini
açıp yanıma koymadım. Tasarımı kendi anlayışımdan türettim — bu, denetim
yapmaktan ucuzdur — ve ucuz yolu seçtiğimi de söylemedim.

Sonuç: `digest`, `memory`, `tool` ve hook hiçbir fazda karşıma çıkmadı. Onbir faz
bittikten sonra, özellik bazında karşılaştırma yapılınca göründüler.

**Dersin genel hâli: bir yeniden yazımın ölçütü ilke değil envanterdir.** İlke
neyin nasıl yapılacağını söyler; neyin yapılacağını söylemez. İkisini karıştıran
bir plan, kendi içinde tutarlı ve eksik olur — ve eksik olduğu, tutarlı olduğu
için fark edilmez.

## `keep` — doktrini bozmayan tek desen

`fallback` desenleri en sert dille reddediyor. `keep` bir desen. Çelişki değil,
çünkü fark **kimin deseni olduğu**:

- Aracın icat ettiği bir desen **yargıdır**: yarım bildiği dillerde hangi satırın
  önemli olduğuna karar verir ve kendinden emin biçimde yanılır.
- Çağıranın yazdığı bir desen **taleptir**: ne aradığını o biliyor, araca düşen
  onu kaybetmemek.

İki uygulama detayı bu ayrımdan çıkıyor:

**Bütçeden sonra uygulanıyor.** Tavan aracın görüşü, `keep` çağıranın talimatı.
Bir varsayılanın talimatı sessizce ezmesi, talimatın hiç olmamasından kötüdür.

**Derlenmeyen desen düz metin olarak aranıyor.** `main()` yazan kişi o
karakterleri kastetti. Hatalı bir gruba sessizlikle cevap vermek, talebi hiç
söylemeden düşürmektir — ve çağıran bunu fark edemez.

## Bu fazın dersi

**Aracın icat ettiği kural ile çağıranın verdiği talimat aynı şey değildir.**

İkisi de "desen" gibi görünür. Biri bilgi taklidi yapan tahmindir, diğeri
bilginin ta kendisidir. Bir tasarım kuralını "desen yasak" diye ezberlemek, bu
farkı görememek demektir.
