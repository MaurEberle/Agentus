# Kontrol paneli

Başlangıç sayfası. Kurulum, etkin ağ ve son çalıştırmaları özetler. **Canlı izleme** veya arşiv değildir — bunun için ayrı sayfalar vardır.

## Kurulum

**Kurulum** kartı ilk çalıştırma için bir şey eksikse görünür, örneğin:

- Ollama’ya erişilemiyor → **Çalışma zamanını denetle** bağlantısı
- Yardım profilinde sağlayıcı veya model yok → **Yardımı yapılandır**
- Henüz ağ yok → **Yeni ağ** veya **Ağ içe aktar**

Ortam tamamsa kart kaybolur. Sessiz kurulumda çekilmeyen isteğe bağlı modeller ikinci bir asistan değildir: Runtime ping veya yardım sohbeti hatayı gösterir.

## Ana bilgisayar kaynakları

**İzleme**’dekiyle aynı kart: **bu PC’nin** CPU, bellek ve GPU/VRAM değerleri, yalnızca uygulama süreci değil. Değerler etkin çalıştırma olmasa da sürekli güncellenir.

## Durum

Hizmetin **durdurulmuş**, **başlıyor**, **çalışıyor** veya **duruyor** olduğunu ve etkin ağı gösterir. Bilgi dizini oluşurken durum **Bilgi dizini oluşturuluyor** ve düğüm adını gösterir. Aynı satır Başlat düğmesindedir. Çalışan ağda: **İzleme** bağlantısı ve isteğe bağlı «… beri çalışıyor». Hızlı seçim yoksa: uyarı ve **Kitaplık** bağlantısı.

Başlat ve durdur **başlık çubuğunda** kalır, bu kartta değil.

## Etkin ağ

Ad, düğüm/kenar sayısı, Geçerli/Geçersiz, son değişiklik. Eylemler: **Düzenle** (düzenleyici), **Kitaplık**, **Yeni ağ**.

Geçersiz, düzenleyicideki doğrulamanın başarısız olduğu anlamına gelir (örneğin bir LLM düğümünde model yok). Bu ağları başlatmamalısın.

## Son kullanılanlar

Kayıtlı ağların son kullanıma göre kısa listesi. Tıklayınca düzenleyici açılır. Boş: henüz ağ yok.

## Son çalıştırmalar

Geçmişteki en yeni kayıtlar (başarı, hata, iptal, zaman aşımı veya hâlâ çalışıyor). Çalışan kayıt **İzleme**’ye, bitenler **Geçmiş**’e gider. Geçmiş deposu bozulursa **Veri** bağlantılı bir uyarı çıkar.

## Son 7 gün

Küçük istatistik: çalıştırma sayısı, başarılı, başarısız. Süzgeç ve grafikler için **Geçmiş** bağlantısı. Bu bir özet, ikinci bir arşiv değil.

## Ortam

- Ollama erişilebilir mi, kabaca model sayısı
- Depo sorunları (ayarlar, yardım, çalışma alanı, geçmiş)
- Yardım yedek modele geçtiyse **tasarruf kipi**

Bağlantılar: **Veri**, çalışma zamanı.

## Hızlı erişim

**Yeni ağ**, **İçe aktar** (kitaplık), **Çalışma zamanı**. Aynı eylemler gezinme ve Ayarlar’da da vardır.
