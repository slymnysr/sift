# 27 — Windows: CI'ın gösterdiği iki gerçek hata

**Nereden çıktı:** Yayın için ilk kez GitHub Actions koştu. Linux ve macOS
yeşildi; **Windows kırmızıydı.** Kullanıcıya seçenek sunuldu — düzelt, ya da
Windows'u matristen çıkarıp desteklemediğimizi yaz — ve düzeltmeyi seçti.

Üç turda 12 hata çıktı. Onu test varsayımıydı. **İkisi aracın kendisiydi**, ve
ikisi de yalnız Windows'ta ortaya çıkan cinstendi: kimse o platformda
koşturmadığı sürece görünmezlerdi.

## Araç hatası 1: "yaşıyor mu?" sorusu öldürüyordu

`background.alive()`, bir arka plan koşusunun gözetmeninin hâlâ orada olup
olmadığını soruyordu. Yöntemi `os.kill(pid, 0)` idi ve docstring'i bunu şöyle
savunuyordu:

> *sinyal 0 soruyu sorar, cevaplamaz: sürecin var olduğunu ve ona sinyal
> gönderebileceğimizi denetler, hiçbir şey teslim etmez.*

POSIX'te doğru. **Windows'ta yanlış.** Orada `os.kill`, `CTRL_C_EVENT` ve
`CTRL_BREAK_EVENT` dışındaki her sinyali `TerminateProcess`'e çevirir ve sinyal
numarasını çıkış kodu yapar. Yani sinyal 0 bir soru değil, **çıkış kodu 0 ile
idam**.

Sonucu testle sınırlı değildi:

| komut | ne yapması gerekiyordu | Windows'ta ne yapıyordu |
|---|---|---|
| `sift list` | koşuları listele | **hepsini öldür** |
| `sift follow` | build'i oku | **build'i öldür** |

Bir yoklama fonksiyonunun idam emrine dönüşmesi, ve bunu kimsenin fark etmemesi
— çünkü CI'ın Windows ayağı ilk kez bugün koştu.

**Düzeltme:** soruyu Windows'un sorduğu gibi sormak.
`OpenProcess(SYNCHRONIZE)` ile tanıtıcı aç, `WaitForSingleObject(handle, 0)`
ile beklemenin hemen dönüp dönmeyeceğine bak. Çıkmış süreç sinyallidir; koşan
süreç değildir ve bekleme derhal zaman aşımına uğrar. `ctypes` stdlib'de,
bağımlılık eklenmedi.

## Araç hatası 2: `~` Windows'ta başka yerde

Testlerin izolasyonu `HOME`'u geçici dizine taşıyordu. Linux ve macOS'ta bu
yeterli. **Windows'ta `Path.home()` `HOME`'a bakmaz** — `USERPROFILE`'a, sonra
`HOMEDRIVE` + `HOMEPATH`'e bakar.

Yani izolasyon üç platformun ikisinde çalışıyordu, ve çalışmadığı üçüncüsü tam
da testlerin geliştiricinin gerçek `~/.config/nvidia/api_key` dosyasını
okuyabileceği platformdu.

Bu, aynı oturumun **dördüncü** aynı-şekilli kusuru:

| # | ne sızıyordu | neden |
|---|---|---|
| 1 | Kullanıcının gerçek deposu | `test_lines.py` `SIFT_HOME` koymuyordu |
| 2 | Gerçek ağ ve kota | anahtar `HOME` dışından okunuyordu |
| 3 | Sessizce zayıf görünüm | `SIFT_NO_MODEL` ile "anahtar yok" karışıyordu |
| 4 | **Windows'ta gerçek anahtar** | `HOME` taşınıyor, `USERPROFILE` taşınmıyordu |

Dördünde de düzeltme `conftest.py`'ye gitti. Ders aynı: **"bir sonraki dosyada
unutma" bir düzeltme değildir.**

## Test varsayımları

Onu da tek bir kökten çıktı: testler `python -c "print(...)"` çağırıyordu.
Python'un metin katmanı Windows'ta iki şey yapar — her `\n`'i `\r\n` yapar, ve
konsolun kod sayfasıyla kodlar. cp1252 ise bu projenin doğrultulduğu
alfabelerin çoğunu yazamaz.

Yani **"bayt bayt" iddiasında bulunan bir test, `print` çağırdığı anda aracın
değil platformun görüşünü ölçüyordu.** Düzeltme: spawn edilen komut
`sys.stdout.buffer`'a yazsın. Kod ASCII olarak gider (`repr` baytları kaçırır),
yani komut satırı da bozamaz.

Bir de korpus: git'in `core.autocrlf`'i Windows'ta örnek dosyalarını
dönüştürüyor ve `cargo-de` örneği "`str.splitlines()` yanlış sayar" iddiasını
kanıtlayamaz hâle geliyordu. `.gitattributes` ile örnekler `-text`: **korpus
veri, kaynak değil; baytı ölçümün kendisi.**

## Mutasyon bataryası neden bu fazda susuyor

`_running_on_windows` platforma özgü. Linux'ta o dal hiç çalışmadığı için
mutasyonu **hiçbir zaman yakalanamaz** — batarya "ESCAPED" derdi ve bu, kuralın
korumasız olduğunu değil, ölçümün orada yapılamadığını söylerdi. Yanlış bir
sayıyı doğru gibi basmaktansa yazmamak daha dürüst.

O dalın tek sınayıcısı CI'ın Windows ayağı. Bu fazın kanıtı bataryada değil,
matriste.

## Ders

**Bir platformu CI matrisinde tutmak, orada çalıştığını iddia etmektir.** İki
seçenek vardı: iddiayı geri çekmek (beş dakika) ya da doğrulamak (üç tur). İkisi
de meşruydu; ama iddia geri çekilseydi `sift list`'in Windows'ta koşuları
öldürdüğü bugün de bilinmeyecekti.
