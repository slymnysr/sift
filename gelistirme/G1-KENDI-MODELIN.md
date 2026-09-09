# G1 — Anahtar tek yol olmasın

**Tarih:** 9 Eylül 2026 · **Durum:** bitti

## Bulgu

```python
@property
def available(self) -> bool:
    return bool(self.api_key)
```

`SIFT_BASE_URL` yıllardır orada duruyordu — yani sift'i kendi uç noktana
yöneltebiliyordun. Ama yerel model sunucularının hiçbiri anahtar istemez:
Ollama, llama.cpp, vLLM, LM Studio, LocalAI, şirket ağ geçidi. Hepsi
`POST /v1/chat/completions` konuşur ve hiçbirinde faturalandırılacak kimse
yoktur.

Sonuç: `SIFT_BASE_URL=http://localhost:11434/v1` yazmış biri, sunucusu ayakta
çalışırken determinist yedeği alıyor ve nedenini **`no api key`** diye okuyordu.
Üstelik 24. faz gereği MCP tarafında araçlar reddediyordu — "kurulumu bitmemiş
makine" muamelesi. Oysa o makinenin kurulumu bitmişti; sadece bizim
bakmadığımız bir yere bitmişti.

## Değişen kural

Eskiden: *anahtar var mı?*
Şimdi: **sorulacak bir yer var mı?** — anahtar **ya da** kişinin kendi yazdığı
adres.

İkisi alternatif, çift değil. Varsayılan uç nokta faturalandırıyor, o yüzden
anahtar istiyor ve anahtarsız makine gerçekten yarım kalmış bir kurulumdur.
Kişinin kendi yazdığı adres bunun tam tersi: **nereye sorulacağını o söyledi**,
oranın kimlik doğrulamadan ne istediği ikisinin arasındadır.

```python
def somewhere_to_ask() -> bool:
    return find_key() is not None or own_endpoint() is not None
```

Üç çağıran da bunu soruyor artık: komut satırının afişi, kancanın teklifi, ve
MCP sunucusunun reddi.

## Yan etki: `Bearer None`

Başlık koşulsuz kuruluyordu:

```python
"Authorization": f"Bearer {self.api_key}"
```

Anahtar yokken bu, tam harfiyle `Bearer None` dizesini gönderiyor. Bizim uç
noktamız aldırmaz; başkasının sunucusunun bir fikri olabilir, ve o fikir
"401" olabilir. Artık anahtar varsa gönderiliyor, yoksa başlık hiç yok.

## Testler

Yedi yeni test, ikisi teeth:

| test | ne kanıtlıyor |
|---|---|
| `..._own_endpoint_is_asked_without_a_key` | Adres verilmişse soru gerçekten gidiyor |
| `..._carries_no_authorization` | Anahtarsız istekte başlık yok |
| `a_key_is_still_carried_when_there_is_one` | **Teeth:** başlığın görünebildiği kanıtlanıyor |
| `the_address_goes_where_it_was_pointed` | Sorulan adres, faturalandıran değil |
| `somewhere_to_ask_is_either_of_the_two` | İki yolun ikisi de yol |
| `a_blank_address_is_not_an_address` | Boş değişken "ayarlanmamış" demektir |
| `..._own_model_is_enough_to_be_set_up` | MCP artık reddetmiyor |
| `the_banner_is_not_printed_to_somebody_running_their_own_model` | Afiş çıkmıyor, komut yine çalışıyor |

Mutasyon bataryasına üç kural eklendi (üçü de yakalandı), ve anahtar kontrolüne
bağlı dört eski çapa yeni satırlara taşındı — dördü de hâlâ yakalıyor.

`conftest.py` bir şey daha siliyor artık: `SIFT_BASE_URL` ve `SIFT_MODELS`.
Sebep listenin geri kalanıyla aynı — ortamda kalmış bir adres, bütün suite'i
sessizce "kurulumu bitmiş makine" testine çevirirdi.

## Ne sınandı, ne sınanmadı

Sınanan: **şekil.** Kendi uç noktası gösterilmiş bir sift'in soruyu gerçekten
sorduğu, ve anahtarsız sorduğu.

Sınanmayan: belirli sunucular. Bu makinede yerel model sunucusu yok (`ollama`,
`llama-server`, `vllm` — üçü de kurulu değil). README bunu olduğu gibi yazıyor:
hangi yerel modelin **iyi** cevap verdiği, çalıştırdığın modele bağlı bir soru,
ve `test/budget.py` onu kendi modelin için ölçmenin yolu.
