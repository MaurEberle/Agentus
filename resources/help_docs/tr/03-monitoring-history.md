# İzleme ve geçmiş

**İzleme** = şimdi, bir çalıştırma. **Geçmiş** = arşiv ve istatistik. Geçmiş **ikinci bir kontrol paneli** veya canlı günlük değildir. Başlat ve durdur **başlık çubuğunda** kalır.

## Canlı ve arşiv

| | İzleme | Geçmiş |
|---|------------|----------|
| Ne zaman | hizmet başlar, çalışır veya durur | çalıştırma bittikten sonra (ve hâlâ çalışırken bağlantı) |
| Grafik | mini grafik, yalnızca okuma, düğüm durumu | kayıtlı anlık görüntü, canlı güncelleme yok |
| Günlük | akış, en yeni üstte, duraklatılabilir | sabit satırlar, süzülebilir |
| Sohbet | çalıştırma sohbeti, yalnızca çalışırken | kayıtlı döküm, devam yazılmaz |

Hâlâ çalışan bir geçmiş kaydı yalnızca İzleme’ye atlamadır («Canlı görüntüle»).

## Çalıştırma olmadan izleme

Etkin çalıştırma yoksa sayfa **son kaydedilen çalıştırmayı** okumak için gösterir (grafik, etkinlik, günlük, sohbet). Bir uyarı hiçbir şeyin canlı olmadığını söyler. Sayfa yalnız hiç çalıştırma kaydı yoksa tamamen boştur: **Çalıştırma yok**, artı etkin ağ veya hızlı seçimin boş olduğu uyarısı. Bağlantı kesildi / hata / başlıyor / duruyor ayrı metinlere sahiptir. Bilgi dizini oluşurken başlangıç uyarısı o düğümün adına döner. Son değerler bağlantı kurulana kadar soluk kalabilir.

## Çalıştırma sırasında

Üst alan: çalıştırma kimliği, başlangıç saati, süre, kaba adım, etkin LLM’ler (yerel / bulut).

**Ağ (yalnızca okuma):** aynı grafik, duruma göre düğüm renkleri (boşta, bekliyor, çalışıyor, bitti, hata). Bir düğüme tıklamak günlük/etkinliği süzgeçler ve ayrıntıyı açar (rol, durum, LLM/araç/giriş/dizin bekleniyor, son ileti, belirteç). Düzenleme yok, ikinci düzenleyici yok.

Bir ajana bilgi bağlıysa başlangıç, dizin oluşurken çalıştırmayı gösterir: bilgi düğümü bekleme nedeni **dizin** ile çalışır, günlük okumayı ve gömmeleri adlandırır, başlık ve kontrol paneli aynı adı gösterir. Zaten güncel bir dizin atlanır ve yalnızca güncel diye not edilir.

**Etkinlik:** geçerli düğümler, «adım x / y» ilerleme, giriş/çıkış belirteçleri, isteğe bağlı bağlam penceresi.

**Ana bilgisayar kaynakları:** **bu PC’nin** CPU, RAM, GPU/VRAM değerleri, yalnızca uygulama değil. Yerel GPU yoksa (bulut çalıştırmalarında tipik) bir uyarı çıkar, hata değil.

## Ağ sohbeti (izleme)

**Sohbet** sekmesi: çalışan grafiğin konuşması. Yalnızca çalıştırma sürerken etkin. Orkestratör yoksa sohbet ilk satırı bekler ve zincire verir. Orkestratör varken yalnız onunla konuşursun. Çalıştırma yalnız bir soruda bekler. Ajan metinleri ve iç komutlar burada görünmez.

Bu **yardım baloncuğu değildir**. Geçmiş ve araçlar ağındır.

## Günlük (izleme)

**Günlük** sekmesi: düzey (hata ayıklama, bilgi, uyarı, hata), düğüm, saat. En yeni üstte. Duraklat takip etmeyi durdurur; «En yenilere git» yine sona atlar. Süzgeçler: arama, düzeyden itibaren, bir düğüm, yalnızca hatalar. Görünen satırları dışa aktar.

Yükler ve iletiler sırları **maskeler** (örneğin `Bearer`, anahtar önekleri). Filtresiz iletme.

## Geçmiş

Şerit: Yenile, seçili çalıştırmaları sil, günlükleri dışa aktar, saklama süresine göre eskileri temizle (Ayarlar → Veri, varsayılan 90 gün).

**Tek süzgeç** her şeyi yönetir: aralık (bugün, 7/30 gün, başlangıç–bitiş), ağ, model, arama (çalıştırma kimliği, ağ, hata). KPI, «güne göre çalıştırmalar» grafiği, sık hatalar, Geçmiş / Modele göre / Ağa göre sekmeleri ve liste aynı süzgeci kullanır.

## Bir çalıştırmanın sonuçları

| Sonuç | Anlam |
|----------|-----------|
| Çalışıyor | hâlâ etkin — geçmişte yalnızca bağlantı |
| Başarı | normal bitti |
| Hata | adım veya hizmet başarısız |
| İptal | başlıktan Durdur, pencere kapandı veya uygulama bitti (çökmeden sonra sonraki başlangıçta da) |
| Zaman aşımı | süre aşıldı |

**İptal hata değildir.** Zaman aşımları ve iptaller KPI’larda ayrı sayılır («Hata» dipnotu).

## Çalıştırma ayrıntısı

Sağ taraf veya ayrı görünüm: meta, mini grafik, **Günlük**, **Adımlar**, **Sohbet** sekmeleri. Adımlar: düğüm, rol, durum, hata. Sohbet: döküm, salt okunur. Tek günlük dışa aktar.

Geçmiş kayıtlarını silmek kayıtlı ağları değiştirmez.
