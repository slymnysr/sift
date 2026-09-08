# Faz 16 — Hafıza

## Fazın cümlesi

Bu makinede bu komut kaç kez çalıştı, nasıl gitti, hangisi bir kez bile
çalışmadı. Kullanıcının gerçekten sorduğu soru şu: **bu bozuk mu, yoksa ben mi?**

## Bu fazın modeli hiç kullanmaması bir eksiklik değil, tasarımdır

Sorunun her parçası sayma işidir. Sayan bir model daha yavaştır, bir istek harcar
ve bazen yanılır; soruda ona verecek bir yargı yok.

Yine de çağırmak, projenin gurur duyduğu aracı yanlış yere sokmak olurdu — ve bu,
kural motorunun hangi satırın önemli olduğuna karar vermesiyle **aynı hata,
sadece ters yönde**.

Bu yüzden bu fazın kuralı projenin geri kalanının aynadaki hâli:

> **Model, hesaplanamayanı karara bağlar. Başka hiçbir şeyi.**

Testi de doğrudan bu: `memory` çağrıldığında `Bridge` kurulursa test kırmızıya
döner.

## Görebildiği kadarı

Kayıt, baytların yanında duruyor — ayrı bir defterde değil. Bunun bedeli:
silinmiş bir yakalama kendi kaydını da götürür, dolayısıyla hafıza yalnız
diskte kalanı bilir.

Bedeli ödemeye değer, çünkü karşılığı şu: **bir yakalamayı silmek gerçekten
siliyor.** Ayrı bir defter tutan bir araçta "sildim" demek, verinin bir kopyasının
başka yerde durduğu anlamına gelir.

Cevabın altında kaç koşu üzerinden konuşulduğu yazıyor. "Bu burada hiç
başarısız olmadı" cümlesi dört yüz koşudan sonra bir şey, iki koşudan sonra
hiçbir şey ifade eder.

## Bu fazın dersi

**Bir aracı her yerde kullanmak, onu doğru yerde kullanmamakla aynı kapıya
çıkar.**
