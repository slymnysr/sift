# G7 — Windows'ta ağacı bitirmek

**Tarih:** 9 Eylül 2026 · **Durum:** bitti, CI'ın Windows ayağında yeşil

## Sorun bir eksiklik değil, bir iddiaydı

README şunu diyordu:

> `sift stop 9f2c41ab` — ends it, and everything it started

Windows'ta doğru değildi. Orada süreç grubu yok; `_signal` tek bir `os.kill`
yapıyordu, ve komutun başlattığı her şey — bir derlemenin dört derleyicisi, bir
test koşucusunun işçileri — kimsenin okumadığı bir dosyaya yazmaya devam
ediyordu. Bunu sınayacak beş test de orada **atlanıyordu**, yani iddia yanlış
olduğu gibi sınanmıyordu da.

## Windows'un grup yerine sahip olduğu şey

İş nesnesi (job object). Süreçler bir işe konur, iş bitirilir, içindeki her şey
gider. `src/sift/jobs.py` bunu iki karara bağlı olarak kullanıyor:

**Ad.** `sift stop` dakikalar sonra, başka bir süreçte koşuyor; aralarında bir
handle taşınamaz. Ad taşınır: koşunun kendi tutamacı `Local\sift-<handle>`
oluyor, durduran onu adıyla açıyor.

**Kapanınca öldürmemek.** Windows, son handle gidince işteki her şeyi
bitirebilir (`KILL_ON_JOB_CLOSE`) ve bu istenmiyor. Gözcüsü öldürülmüş bir koşu
bilerek çalışmaya devam eder — baytlar gelmeye devam eder, `stop` sonunu kendi
yazmaya hazırdır. Açsaydık Windows, gözcüyü öldürmenin işi de öldürdüğü tek
platform olurdu.

**Gözcü işin dışında.** Bu da tesadüf değil: iş bitince gözcü hayatta kalıyor,
komutun gittiğini görüyor ve sonu kendisi yazıyor. Ona sinyal göndermek daha
kötüydü — Windows'ta `SIGTERM` zaten `TerminateProcess`, yani koşunun nasıl
bittiğini kaydedebilecek tek süreç, kaydedemeden ölüyordu. Eskiden aynen bu
oluyordu.

## CI iki gerçek hata gösterdi

Bu makine WSL; sınama 27. fazdaki gibi `windows-latest` üzerinde yapıldı. İlk
tur iki testte kırmızı döndü ve ikisi de haklıydı.

**Bir: komut işe hiç atanmamıştı.** `joined` çağrısını yalnız `watch.py`'ye
koymuşum; `capture.run` işi kuruyor ama boş bırakıyordu. Zaman aşımında boş bir
iş bitiriliyor, `TerminateJobObject` **başarı** dönüyor, ve o "başarı" yüzünden
`proc.kill()` hiç çağrılmıyordu. Komut yaşamaya devam ediyor, `proc.wait(5)`
doluyor, pompa 64 KB'lık okumasında asılı kalıyor: 1,5 saniyelik bir zaman
aşımı 8,5 saniye sürüyor ve **çıktı da kayboluyordu**.

Ders: işi bitirmekle süreci öldürmeyi **birbirinin alternatifi** saymak hataydı.
Artık `_stop` ikisini birden yapıyor. Boş bir işi bitirmek, komutu bitirmek
değildir.

**İki: test kendi sorgusunu sayıyordu.** Windows'ta `pgrep` yok, WMI sorgusu
kullandım — ama token'ı komut satırına yazınca sorgu süreci kendisiyle
eşleşiyor. `_alive` her zaman en az bir süreç buluyordu; test hiçbir koşulda
geçemezdi. Token artık ortam değişkeninde gidiyor.

İkinci tur: **6/6 yeşil**, iki Windows ayağı dahil.

## Sınananlar

| test | ne diyor |
|---|---|
| `test_stopping_a_run_ends_what_the_command_itself_started` | Artık Windows'ta da koşuyor. Torun süreç dosyaya yazmayı bırakıyor mu |
| `test_a_timeout_kills_the_children_the_command_started` | Aynı soru, ön plandaki zaman aşımı için |
| `test_the_job_object_path_is_inert_where_there_are_process_groups` | POSIX'te hiçbir şeye mal olmuyor mu |
| `test_a_job_can_be_made_and_ended_on_windows` | Teeth: mekanizma bir yerde gerçekten var mı |

Bataryaya bir kural: Windows'a özel kodun her yerde atıl kalması. `ctypes.WinDLL`
Linux'ta hiç yok — oraya varmak yanlış cevap değil, bir koşuyu bitirirken alınan
`AttributeError`. Yakalandı.

**Bilerek eklenmeyen ikinci kural:** işi bitiren satırın mutasyonu. Linux'ta
`jobs.end` False döndüğü için o mutasyon aynı davranır ve her seferinde kaçardı.
Bataryanın kıramayacağı bir kuralı korumuş gibi göstermesi bataryayı yalancı
yapar. Onu koruyan şey CI'ın Windows ayağı, ve bu böyle yazıldı.

## Eskiyen cümleler

İki docstring artık yanlış olduğu için düzeltildi: `_new_session` "Windows'ta
yalnız çocuğun kendisi durdurulur, dürüst sınır budur" diyordu, `_pump_until_closed`
da ona atıf yapıyordu. İkisi de G7'den sonra doğru değil.
