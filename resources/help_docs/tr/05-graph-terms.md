# Terimler

Yardım sohbeti ve düzenleyici için kısa sözlük.

## Grafik / ağ

Düğüm ve kenarlardan oluşan kayıtlı belge. Düzenleyicide düzenler, kopyaları kitaplıkta yönetirsin. **Etkin** ağ hızlı seçimdeki ağıdır — **Başlat** yalnızca onu başlatır.

## Çalıştırma (run)

Etkin grafiğin bir yürütmesi. En fazla **biri** çalışır. Başlat ve durdur başlıkta. Sonuçlar: çalışıyor, başarı, hata, iptal, zaman aşımı.

## Düğümler ve kenarlar

Parçalar (sohbet girişi, ajan, LLM, araç, bilgi, yönlendirici, son) ve tipli bağlantılar. Kutular arasında rastgele oklar geçersizdir.

## Ajan

Sistem istemi olan düğüm. Model, ileti, araçlar ve bilgi bağlantı noktalarından gelir, gömülü anahtar olarak değil.

## LLM düğümü

Sağlayıcı ve modeli seçer. Yerel Ollama, yoksa bulut veya OpenAI uyumlu URL artı kimlik bilgisi.

## Sohbet girişi

Çalıştırmada kullanıcı metninin tek girişi. Ağ başına en fazla bir. İzleme sohbeti buraya yazar.

## Araç

First-party (HTTP, web araması, tarih/saat, hesap makinesi) veya MCP. Yapılandırma denetçide, yürütme yalnızca çalıştırmada.

## Bilgi (ağ)

Knowledge düğümü: uygulamanın veri klasörünün **altında** bir klasör. Kendi dizini, topK ve puan. **Yardım derlemi değil.** Sürücü kökü değil.

## Yardım-RAG

Veri klasöründeki yardım klasöründeki belgeler (varsayılan kılavuzlar artı Markdown’ların). Yalnızca yardım sohbet botu. Değişiklikten sonra Ayarlar → Yardım sohbeti altında dizini yeniden oluştur.

## Kimlik bilgisi / credential

Windows kasasında saklanan anahtar. Listelerde yalnızca maske. Grafikte yalnızca kimlik/seçim, asla sır. Dışa aktarım parola içermez.

## MCP

Model Context Protocol: dış araç sunucuları. Ayarlar’da oluşturup etkinleştir, grafikte MCP türünde araç düğümü olarak bağla. Yardım MCP kullanmaz.

## Sağlayıcı

`ollama` (yerel), `xai`, `openai`, `anthropic` (Claude), `gemini` (bulut, önce API anahtarı, sonra model listesi), `openai_compat` (kendi uyumlu HTTP API’si, örn. LM Studio).

## Ollama

Yerel modeller için ayrı hizmet. Uygulama istemcidir. Kurulum Ollama ve iki küçük varsayılan model oluşturabilir. Uygulamayı kapatmak Ollama’yı çalışır bırakır.

## Kontrol paneli, izleme, geçmiş

Kontrol paneli = özet ve kurulum. İzleme = canlı. Geçmiş = arşiv. Aynı sayfa üç kez değildir.

## Geçerli / geçersiz

Grafiğin doğrulanması. Geçersiz kaydedilebilir ama başlatmaya uygun değildir. Yalnızca geçerli bir ağ etkin yapılabilir.

## Hızlı seçim

Başlıkta etkin ağ seçimi. Kitaplıktaki «Etkin yap» ile aynıdır.

## Tasarruf kipi

Ana model taşımazsa yardım yedek modele geçer. Kontrol paneli bunu Ortam altında gösterebilir.

## Taşınabilir

EXE’nin yanında `portable.txt`: veriler uygulamanın yanında. Kurulu kopya: veriler uygulama veri klasöründe, programlar ayrı.
