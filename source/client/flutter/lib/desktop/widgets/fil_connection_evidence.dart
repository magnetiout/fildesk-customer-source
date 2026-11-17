/// Native snapshot only. Readiness, peer trust and access permission are distinct.
class FilConnectionEvidence {
  final Map context;
  final String build;
  final Map? service;
  final List<Map> outgoing;
  FilConnectionEvidence._(
      this.context, this.build, this.service, this.outgoing);

  static FilConnectionEvidence? parse(dynamic raw) {
    if (raw is! Map ||
        raw['version'] != 1 ||
        raw['context'] is! Map ||
        raw['build'] is! String ||
        raw['outgoing'] is! List) return null;
    final ctx = raw['context'] as Map;
    if (!['customer', 'operator', 'fallback'].contains(ctx['role']) ||
        ctx['endpoint'] is! String ||
        ctx['key_fingerprint'] is! String) return null;
    bool same(dynamic other) =>
        other is Map &&
        ['role', 'endpoint', 'key_fingerprint']
            .every((key) => other[key] == ctx[key]);
    final service = raw['service'];
    Map? validService;
    if (service is Map &&
        same(service['context']) &&
        service['registration_ack'] is bool &&
        service['online'] is bool &&
        (service['pending_approval'] == null || (service['pending_approval'] is int && service['pending_approval'] >= 0 && service['pending_approval'] <= 64)) &&
        service['sessions'] is List &&
        (service['sessions'] as List).every((s) =>
            s is Map && s['encrypted'] is bool && s['reference'] is String))
      validService = service;
    final sessions = <Map>[];
    for (final s in raw['outgoing']) {
      if (s is! Map ||
          !same(s['context']) ||
          s['round'] is! int ||
          s['reference'] is! String ||
          ![
            'requesting',
            'authorization_pending',
            'authorized_waiting_video',
            'video_packet_received',
            'verification_failed',
            'configuration_failed'
          ].contains(s['phase']) ||
          (s['encrypted'] != null && s['encrypted'] is! bool) ||
          (s['direct'] != null && s['direct'] is! bool) ||
          s['stream_type'] is! String ||
          !['not_evaluated', 'unknown', 'pinned_root_peer_signature', 'failed']
              .contains(s['peer_identity'])) continue;
      if (s['peer_identity'] == 'pinned_root_peer_signature' &&
          s['encrypted'] != true) continue;
      sessions.add(s);
    }
    return FilConnectionEvidence._(ctx, raw['build'], validService, sessions);
  }

  bool get operatorRole => context['role'] == 'operator';
  bool get registered =>
      !operatorRole &&
      service?['online'] == true &&
      service?['registration_ack'] == true;
  List get incoming => service?['sessions'] as List? ?? const [];
  String? get sessionLabel {
    if (outgoing.any((s) => s['phase'] == 'configuration_failed'))
      return 'Sunucu anahtarı yapılandırması geçersiz';
    if (outgoing.any((s) => s['phase'] == 'verification_failed'))
      return 'Karşı cihaz kimliği doğrulanamadı';
    if (incoming.isNotEmpty) return 'Yetkili destek oturumu var';
    if (outgoing.isEmpty) return null;
    if (outgoing.any((s) => s['phase'] == 'video_packet_received'))
      return 'Yetkili oturum · görüntü verisi alındı';
    if (outgoing.any((s) => s['phase'] == 'authorized_waiting_video'))
      return 'Oturum yetkili · görüntü bekleniyor';
    if (outgoing.any((s) => s['phase'] == 'authorization_pending'))
      return 'Parola veya müşteri onayı bekleniyor';
    return 'Destek bağlantısı başlatılıyor';
  }

  String get details {
    final lines = <String>[
      'Rol: ${operatorRole ? 'Operatör (gelen erişim kapalı)' : 'Müşteri'} · $build',
      'Sunucu: ${context['endpoint']}',
      'Kayıt: ${operatorRole ? 'bu rol için uygulanmaz' : service == null ? 'bilinmiyor; native hizmet yanıtı bekleniyor' : registered ? 'kayıt yanıtı alındı; sunucu kimlik kanıtı değildir' : 'güncel kayıt onayı yok'}',
      'Sunucu kimliği: NAT/kayıt yanıtı ile doğrulanmaz.',
      'Yapılandırılmış açık anahtar izi: ${context['key_fingerprint']}',
    ];
    if (incoming.isNotEmpty) {
      lines.add(
          'Gelen oturum: ${incoming.length} · native erişim yetkisi verildi.');
      lines.add(
          'Şifreleme: ${incoming.every((s) => s['encrypted'] == true) ? 'native stream anahtarı etkin' : 'en az bir oturumda doğrulanamadı'}');
      lines.add(
          'Operatörün kurumsal kimliği: bu uygulama tarafından doğrulanmıyor.');
      lines.add('Yol / gerçek görüntü ve girdi: bu pencerede ölçülmüyor.');
    }
    for (var i = 0; i < outgoing.length; i++) {
      final s = outgoing[i];
      final authorized = ['authorized_waiting_video', 'video_packet_received']
          .contains(s['phase']);
      lines.add(
          'Dış oturum ${s['reference']}: ${authorized ? 'native LoginResponse ile yetkili' : 'henüz yetki yok'}');
      lines.add(
          'Karşı cihaz anahtarı: ${s['peer_identity'] == 'failed' ? 'DOĞRULANAMADI; bağlantı durduruldu' : s['peer_identity'] == 'pinned_root_peer_signature' ? 'sabit kayıt otoritesi anahtarı → cihaz imzası → oturum anahtarı doğrulandı' : 'henüz doğrulanmış kanıt yok'}');
      lines.add(
          'Şifreleme: ${s['encrypted'] == true ? 'native stream anahtarı etkin' : s['encrypted'] == false ? 'DOĞRULANMADI' : 'henüz değerlendirilmedi'}');
      lines.add(
          'Yol: ${s['direct'] == true ? 'doğrudan' : s['direct'] == false ? 'relay' : 'henüz bilinmiyor'} ${s['stream_type']}');
      lines.add(
          'Video: ${s['phase'] == 'video_packet_received' ? 'paket alındı; ekranda render/girdi kanıtı değildir' : 'henüz paket kanıtı yok'}');
    }
    if (incoming.isEmpty && outgoing.isEmpty)
      lines.add(
          'Oturum: etkin yetki/görüntü kanıtı yok. Kimlik kontrolü henüz değerlendirilmedi.');
    return lines.join('\n');
  }

  bool get insecure =>
      outgoing.any((s) => s['phase'] == 'configuration_failed') ||
      outgoing.any((s) => s['peer_identity'] == 'failed') ||
      incoming.any((s) => s['encrypted'] == false) ||
      outgoing.any((s) => s['encrypted'] == false);
}
