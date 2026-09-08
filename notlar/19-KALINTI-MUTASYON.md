# 19 — Kalıntı mutasyon: testin makineyi kapattığı gün

**Tarih:** 8 Eylül 2026
**Belirti:** Oturum, `pytest` başladıktan ~3 dakika sonra sessizce kopuyor.
Hata mesajı yok, çıktı yok, çıkış kodu yok. Terminal geri geldiğinde her şey
baştan başlamış oluyor.

## Yanlış teşhis

İlk bakışta bu, bu makinede daha önce görülmüş bir şeye benziyordu: WSL bellek
tavanı dolunca Windows'un VM'e `poweroff` göndermesi. Öyle olsaydı Linux
tarafında hiçbir iz kalmazdı — ve gerçekten de kalmamıştı. Teşhis kendini
doğruluyor gibi görünüyordu.

Ölçüm bunu çürüttü:

| Ne | Beklenen (bellek teorisi) | Ölçülen |
|---|---|---|
| `oom_kill` sayacı | >0 | **0** |
| Boş bellek, koşu sırasında | düşer | **4.6 GB, hiç kıpırdamadı** |
| Çekirdek uptime | sıfırlanır | **6s40dk, kesintisiz** |
| Kapanma biçimi | ani | **temiz: oturum çıkışı → logind → poweroff** |

Çekirdek ayaktaydı, systemd PID 1 yeniydi. Yani **VM değil, distro** kapanıyordu.
Ve kapanma zinciri her seferinde aynıydı:

```
oturum kapandı → systemd-logind: "The system will power off now!" → poweroff
→ ~2 dk sonra distro geri geldi
```

Yani makineyi bellek öldürmüyordu. **Oturumu bir şey öldürüyordu**, WSL de son
oturum gidince distro'yu kapatıyordu.

## Gerçek sebep

`test/mutations.py` bir kuralı bilerek bozar, suite'i çalıştırır, dosyayı
`finally` ile geri koyar. `finally` her şeyi karşılar — makine kapanması hariç.

Diskte kalan mutasyon şuydu:

```
kural   : bu aracın başlatmadığı bir pid'e asla sinyal gönderilmez
before  : if running.pid <= 1:
after   : if False:
```

`background.ours` içindeki bu koruma, `stop`'un bir **süreç grubuna** sinyal
gönderdiği için vardır. Koruma kalkınca zincir şöyle işledi:

1. `test_a_marker_naming_pid_one_is_closed_and_never_signalled` pid 1'i işaret
   eden bir işaretçi yazar.
2. Testin kendi assert'i mutasyonu yakalar ve **düşer** — yani mutasyon
   bataryası görevini yapmıştır.
3. Test kendi temizliğine gelemeden bittiği için işaretçi ortada kalır.
4. Fixture'ın teardown'ı kalan koşuları süpürür: `background.stop(...)`.
5. Koruma kapalı olduğundan `ours` "evet, bizim" der ve
   `_signal(1, SIGTERM)` çalışır.
6. tmux, gözcü ve testleri çalıştıran oturum ölür → WSL distro'yu kapatır.
7. Makine kapandığı için `finally` hiç çalışmaz. **Mutasyon diskte kalır.**

### 5. adım göründüğünden kötü: bu bir süreç grubu değil

İlk yazdığımda buraya "süreç grubu 1'e SIGTERM gider" demiştim. Yanlıştı, ve
`ours`'un kendi docstring'i de aynı şeyi yanlış anlatıyordu. Ölçüm:

```
kill(1, 0)    -> PermissionError   (init root, dokunulamaz)
killpg(1, 0)  -> izin var, başarılı
```

Grupta yalnız root systemd varken `killpg` neden geçiyor? Çünkü
`os.killpg(g, s)` aslında `kill(-g, s)`'tir ve POSIX'te **`kill(-1, s)` "grup 1"
demek değildir**: *çağıranın sinyal gönderebildiği her süreç* demektir, yalnız
init hariç. `killpg(1, 0)` başarılı çünkü çağıran en azından kendine sinyal
gönderebiliyor.

Yani bu bir ağacı sonlandırmak değil, **yayın yapmaktır**: kullanıcının sahip
olduğu her şey — terminal, kabuk, gözcü, örnekleyici ve süreci başlatan
`pytest`'in kendisi. Kanıtı log dosyasının bittiği yer: `deneme2.log`

```
collected 1 item
test/test_background.py F
```

`F` var, traceback yok, özet yok. Süreç kendi çıktısını yazarken öldürüldü.

`pid = 0` aynı hatanın sessiz hâli: `getpgid(0)` **çağıranın kendi** grubunu
verir, yani durdurma işini yapan koşuyu durdurur.

7. adım bunu kendi kendini besleyen bir döngü yapar. Bir akşamda altı kez
tekrarlandı; her seferinde bir test sonucu gibi değil, açıklanamayan bir bağlantı
kopması gibi göründü.

Bu senaryo testin docstring'inde zaten yazılıydı — *"terminal çoklayıcısını,
ayrık bir gözcüyü ve testleri çalıştıran oturumu düşürdü"*. Test doğruydu,
koruma doğruydu, batarya doğruydu. Eksik olan tek şey **onarımın ne zaman
çalıştığıydı**.

## Çözüm

`undo_leftover()` zaten vardı ve doğru yazılmıştı: dosyayı yazdığı metinle bayt
bayt karşılaştırır, eşleşiyorsa orijinali geri koyar, eşleşmiyorsa hiçbir şey
yapmaz. Sorun onarımda değil, **çağrıldığı yerdeydi**: yalnız bataryanın kendi
`main`'inden. İnsanların çalıştırdığı şey ise `pytest`.

`test/conftest.py` eklendi. Toplama (collection) öncesinde, her `pytest`
çağrısında çalışır, kalıntıyı geri alır ve ne geri aldığını söyler.

Kontrollü sınama: zararsız bir mutasyon (bir yoruma işaret koymak) uygulanıp
kaydı bırakıldı, `pytest --collect-only` çalıştırıldı.

```
conftest: undid a mutation an earlier run left behind -- lines.py: zararsiz deney
```

Dosya geri yüklendi, kayıt temizlendi.

## İlk çözümün kendi hatası

`conftest.py` yazıldıktan sonra `mutations._run_suite()` okundu ve şu görüldü:
batarya, mutasyonu uygulayıp suite'i **ortamı devralan bir alt süreçte**
çalıştırıyor. Yani `conftest` orada da çalışacak, bataryanın az önce bilerek
uyguladığı mutasyonu "kalıntı" sanıp geri alacak, suite yeşil dönecek ve
`main()` her mutasyon için `ESCAPED` yazacaktı.

Sonuç: %100 yakalayan bir batarya, sessizce "hiçbirini yakalamıyor"a dönerdi —
ve geriye kalan sayı hâlâ bir ölçüm gibi görünürdü. Koruduğu ölçümü kapatan bir
güvenlik ağı, ağ olmamasından kötüdür.

Düzeltme: batarya, suite'i çalıştırırken `SIFT_MUTATING=1` diyor; `conftest` o
işareti görünce kenara çekiliyor. Diskteki kayıt iki durumu ayırt edemez —
ikisinde de aynıdır — o yüzden fark, hâlâ hayatta olan ve kendi işini geri
alabilecek olan taraf tarafından, ortam üzerinden söyleniyor.

## İkinci koruma: tek bir mutasyon felaket olamamalı

Asıl kusur mutasyonun kalması değildi. Asıl kusur, **felaketle aramızda tek bir
satır olmasıydı**. `ours`'taki `if running.pid <= 1` gittiğinde geriye hiçbir şey
kalmıyordu.

`_signal` artık aynı kuralı bağımsız olarak ikinci kez tutuyor: `pid <= 1` ise
hiçbir şey göndermiyor, ve hesaplanan grup 1 ise `killpg` yerine yalnız o pid'e
gidiyor. İki koruma bir kuralı tutuyor, ve bu tekrar değil — noktanın kendisi:

| Sökülen | Ne olur |
|---|---|
| `ours`'taki koruma | `_signal` yayını reddeder → test düşer, makine yaşar |
| `_signal`'daki taban | `ours` pid 1'i reddeder → `_signal` hiç çağrılmaz |

Batarya ikisini de ayrı ayrı bozuyor (`MUTATIONS` içinde üç kural), çünkü bu
özellik ancak ikisi ayrı ayrı sınanırsa gerçekten vardır. Birlikte sınamak,
biri sökülmüşken de yeşil dönerdi.

İlk koşu şunu verdi:

```
baseline  534 passed, 1 skipped
caught     a pid this tool did not start is never signalled
caught     signalling refuses a pid that is a broadcast rather than a tree
ESCAPED    signalling refuses a process group that is a broadcast
caught     a run nobody could signal is closed rather than left open
```

İlk satır bu notun asıl kanıtı: makineyi altı kez süpüren mutasyon artık
"caught" — yani yalnızca bir test düşüyor, oturum ayakta kalıyor.

Üçüncü satır ise yeni yazılan korumanın kendi boşluğu: `if group > 1` yerine
`if True` konduğunda 534 testin hepsi geçiyordu. Yani grup dalını hiçbir şey
tutmuyordu. Batarya, düzeltmeyi yazan kişinin gözden kaçırdığı yeri aynı gün
buldu — ve zaten bunun için var. Eksik test yazıldı
(`test_a_group_that_is_a_broadcast_is_narrowed_to_the_process_itself`).

## Ders

Bu fazın kuralı, projenin geri kalanının kuralıyla aynı: **garanti kodda.**
Mutasyon bataryası "dosyayı geri koyarım" diye söz veriyordu ve o sözü ancak
kendisi hayattaysa tutabiliyordu. Söz, onu tutamayacak koşulları da kapsamalı.

Daha genel hâli: **hatırlanınca çalışan onarım, onarım değildir.** Kurtarma
yolu, kurtarılacak durumun kendisi tarafından tetiklenmelidir — burada bu,
onarımı bataryanın giriş noktasından suite'in giriş noktasına taşımak demekti.

Bir de teşhis dersi var, ve bu ilkinden pahalıya mal oldu: **bilinen bir arıza,
belirtiyi açıkladığı için doğru olmaz.** Bellek teorisi her gözlemi açıklıyordu
çünkü hiçbir iz bırakmamak onun beklenen davranışıydı. Onu çürüten şey daha iyi
bir tahmin değil, `oom_kill = 0` idi.
