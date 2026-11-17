import 'dart:async';
import 'package:flutter/material.dart';
import 'fil_connection_evidence.dart';

/// Read-only observation, never an authentication or remote-control grant.
class FilServerStatus {
  final String state;
  final FilConnectionEvidence? connection;
  const FilServerStatus(this.state, {this.connection});
  FilServerStatus withConnection(dynamic raw) =>
      FilServerStatus(state, connection: FilConnectionEvidence.parse(raw));
  static const connecting = FilServerStatus('connecting');
  static const unavailable = FilServerStatus('identity_unavailable');

  factory FilServerStatus.fromNative(dynamic raw) {
    if (raw is! Map ||
        raw['version'] != 1 ||
        raw['scope'] != 'unsigned_nat_service_only' ||
        raw['identity_verified'] != false ||
        raw['available'] is! bool) {
      return unavailable;
    }
    final state = raw['state'];
    if (state == 'available_unverified') {
      final age = raw['checked_ago_ms'];
      if (raw['available'] != true ||
          age is! int ||
          age < 0 ||
          age > 15000 ||
          raw['reason'] != 'unsigned_nat_response') return unavailable;
      return const FilServerStatus('available_unverified');
    }
    if (raw['available'] != false) return unavailable;
    if (state == 'identity_failed' &&
        raw['reason'] == 'invalid_configuration_key') {
      return const FilServerStatus('identity_failed');
    }
    if (const [
      'connecting',
      'reconnecting',
      'disconnected',
      'identity_unavailable'
    ].contains(state)) return FilServerStatus(state as String);
    return unavailable;
  }

  String get label {
    if (connection?.outgoing.any((s) => s['phase'] == 'configuration_failed') ==
        true) return 'Sunucu anahtarı yapılandırması geçersiz';
    if (connection?.outgoing.any((s) => s['peer_identity'] == 'failed') == true)
      return 'Karşı cihaz kimliği doğrulanamadı';
    if (connection?.insecure == true) return 'Oturum şifrelemesi doğrulanamadı';
    if (connection?.sessionLabel != null) return connection!.sessionLabel!;
    if (state != 'identity_failed' && connection?.registered == true)
      return 'Destek almaya hazır';
    if (state == 'available_unverified' && connection?.operatorRole == true)
      return 'Destek bağlantısı başlatmaya hazır';
    switch (state) {
      case 'connecting':
        return 'Sunucu erişimi kontrol ediliyor';
      case 'reconnecting':
        return 'Sunucu erişimi yeniden kontrol ediliyor';
      case 'available_unverified':
        return 'Destek hazırlığı tamamlanamadı';
      case 'disconnected':
        return 'Sunucu yanıtı alınamadı';
      case 'identity_failed':
        return 'Sunucu anahtarı yapılandırması geçersiz';
      default:
        return 'Bağlantı durumu henüz bilinmiyor';
    }
  }

  String get detail =>
      connection?.details ??
      'Erişim: ${state == 'available_unverified' ? 'NAT yanıtı alındı' : 'henüz güncel kanıt yok'}. '
          'NAT yanıtı kimlik veya oturum yetkisi kanıtı değildir.';
}

/// Bounded bridge polling and local freshness independent of native/FFI progress.
/// A timed-out, uncancellable bridge future remains the single in-flight read;
/// its late completion may release the slot but can never publish stale data.
class FilServerStatusPoller {
  final Future<dynamic> Function() read;
  final void Function(FilServerStatus) onStatus;
  final void Function(Map)? onPayload;
  final Duration timeout;
  bool _busy = false;
  bool _disposed = false;
  int _generation = 0;
  int _observationRevision = 0;
  Timer? _expiry;

  FilServerStatusPoller(
      {required this.read,
      required this.onStatus,
      this.onPayload,
      this.timeout = const Duration(seconds: 3)});

  Future<void> poll() async {
    if (_disposed || _busy) return;
    _busy = true;
    final generation = ++_generation;
    final elapsed = Stopwatch()..start();
    final original = Future<dynamic>.sync(read);
    // Do not clear busy at timeout: Dart cannot cancel a native bridge call.
    original.then<void>((_) {
      _busy = false;
    }, onError: (Object _, StackTrace __) {
      _busy = false;
    });
    try {
      final payload = await original.timeout(timeout);
      if (_disposed || generation != _generation) return;
      final map = payload is Map ? payload : <String, dynamic>{};
      final raw = map['fil_server_status'];
      var status = FilServerStatus.fromNative(raw)
          .withConnection(map['fil_connection_status']);
      _expiry?.cancel();
      final revision = ++_observationRevision;
      if (status.connection != null) {
        _expiry = Timer(const Duration(seconds: 3), () {
          if (!_disposed && revision == _observationRevision)
            onStatus(FilServerStatus.unavailable);
        });
      } else if (status.state == 'available_unverified') {
        final remaining = 15000 -
            (raw['checked_ago_ms'] as int) -
            elapsed.elapsedMilliseconds;
        if (remaining <= 0) {
          status = FilServerStatus.unavailable;
        } else {
          _expiry = Timer(Duration(milliseconds: remaining), () {
            if (!_disposed && revision == _observationRevision) {
              onStatus(FilServerStatus.unavailable);
            }
          });
        }
      }
      onStatus(status);
      onPayload?.call(map);
    } catch (_) {
      if (!_disposed && generation == _generation) {
        _expiry?.cancel();
        _observationRevision++;
        onStatus(FilServerStatus.unavailable);
      }
    }
  }

  void dispose() {
    _disposed = true;
    _generation++;
    _observationRevision++;
    _expiry?.cancel();
  }
}

class FilServerStatusIndicator extends StatelessWidget {
  final FilServerStatus status;
  final bool serviceStopped;
  const FilServerStatusIndicator(
      {Key? key, required this.status, this.serviceStopped = false})
      : super(key: key);

  @override
  Widget build(BuildContext context) {
    final label = serviceStopped && status.connection?.sessionLabel == null
        ? 'Yerel destek hizmeti çalışmıyor'
        : status.label;
    final dark = Theme.of(context).brightness == Brightness.dark;
    // Readiness is not a cryptographic guarantee; no lock icon is used.
    final color = status.connection?.insecure == true ||
            status.state == 'identity_failed' ||
            (status.connection?.sessionLabel == null &&
                status.state == 'disconnected')
        ? Theme.of(context).colorScheme.error
        : dark
            ? const Color(0xFF90CAF9)
            : const Color(0xFF1565C0);
    return Semantics(
      liveRegion: false,
      label: '$label. ${status.detail}',
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
              padding: const EdgeInsets.only(top: 5, right: 10),
              child: Container(
                  width: 8,
                  height: 8,
                  decoration:
                      BoxDecoration(color: color, shape: BoxShape.circle))),
          Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                Text(label, style: const TextStyle(fontSize: 14)),
                const SizedBox(height: 3),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  childrenPadding: EdgeInsets.only(bottom: 8),
                  title: const Text('Bağlantı ayrıntıları',
                      style: TextStyle(fontSize: 12)),
                  children: [
                    ConstrainedBox(
                        constraints: const BoxConstraints(maxHeight: 160),
                        child: SingleChildScrollView(
                            child: Align(
                                alignment: Alignment.centerLeft,
                                child: Text(
                                    '${status.detail}\nSon güncelleme: ${TimeOfDay.now().format(context)} · ${status.state}',
                                    style: const TextStyle(fontSize: 12)))))
                  ],
                ),
              ])),
        ],
      ),
    );
  }
}
