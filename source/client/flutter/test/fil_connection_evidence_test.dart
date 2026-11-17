import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_hbb/desktop/widgets/fil_connection_evidence.dart';
import 'package:flutter_hbb/desktop/widgets/fil_server_status.dart';

Map<String, dynamic> contextFor(String role) => {
      'role': role,
      'endpoint': '127.0.0.1:21116',
      'key_fingerprint': 'public-fixture-fingerprint'
    };
Map<String, dynamic> snapshot(String role,
    {bool registration = false,
    List<Map> outgoing = const [],
    List<Map> incoming = const []}) {
  final ctx = contextFor(role);
  return {
    'version': 1,
    'build': '1.5.0+73',
    'context': ctx,
    'service': {
      'context': ctx,
      'registration_ack': registration,
      'online': registration,
      'sessions': incoming
    },
    'outgoing': outgoing
  };
}

int nextReference = 0;
Map<String, dynamic> session(String role, String phase,
        {bool? encrypted, bool? direct, String identity = 'not_evaluated'}) =>
    {
      'context': contextFor(role),
      'round': 1,
      'reference': (++nextReference).toRadixString(16).padLeft(32, '0'),
      'phase': phase,
      'encrypted': encrypted,
      'direct': direct,
      'peer_identity': identity,
      'stream_type': direct == null ? '' : 'TCP'
    };
FilServerStatus status(Map raw) =>
    const FilServerStatus('available_unverified').withConnection(raw);

Future<void> main() async {
  TestWidgetsFlutterBinding.ensureInitialized();
  final sdk = Platform.environment['FIL_FLUTTER_ROOT'];
  if (sdk != null) {
    final font = FontLoader('Roboto');
    font.addFont(
        File('$sdk/bin/cache/artifacts/material_fonts/Roboto-Regular.ttf')
            .readAsBytes()
            .then((v) => ByteData.sublistView(v)));
    await font.load();
    final icons = FontLoader('MaterialIcons');
    icons.addFont(File(
            '$sdk/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf')
        .readAsBytes()
        .then((v) => ByteData.sublistView(v)));
    await icons.load();
  }
  test(
      'role readiness is independent of NAT identity and optional service fields',
      () {
    final op = status(snapshot('operator'));
    expect(op.label, 'Destek bağlantısı başlatmaya hazır');
    expect(op.detail, contains('bu rol için uygulanmaz'));
    final customer = status(snapshot('customer', registration: true));
    expect(customer.label, 'Destek almaya hazır');
    expect(customer.detail, contains('sunucu kimlik kanıtı değildir'));
    expect(status(snapshot('customer')).label, 'Destek hazırlığı tamamlanamadı');
    expect(FilConnectionEvidence.parse({'version': 1}), isNull);
    expect(
        status({...snapshot('customer'), 'service': null})
            .connection!
            .registered,
        false);
  });
  test(
      'peer trust, session authorization and packet receipt remain distinct and scoped',
      () {
    final secure = session('operator', 'authorization_pending',
        encrypted: true, direct: false, identity: 'pinned_root_peer_signature');
    final pending = status(snapshot('operator', outgoing: [secure]));
    expect(pending.label, 'Parola veya müşteri onayı bekleniyor');
    expect(pending.detail, contains('henüz yetki yok'));
    expect(pending.detail, contains('relay'));
    final authorized = status(snapshot('operator', outgoing: [
      {...secure, 'phase': 'authorized_waiting_video'}
    ]));
    expect(authorized.label, contains('görüntü bekleniyor'));
    final packet = status(snapshot('operator', outgoing: [
      {...secure, 'phase': 'video_packet_received'}
    ]));
    expect(packet.detail, contains('render/girdi kanıtı değildir'));
    expect(
        status(snapshot('operator', outgoing: [
          {...secure, 'context': contextFor('customer')}
        ])).connection!.outgoing,
        isEmpty);
    expect(
        status(snapshot('operator', outgoing: [
          {
            ...secure,
            'context': {
              ...contextFor('operator'),
              'endpoint': '127.0.0.2:21116'
            }
          }
        ])).connection!.outgoing,
        isEmpty);
    expect(
        status(snapshot('operator', outgoing: [
          {
            ...secure,
            'context': {...contextFor('operator'), 'key_fingerprint': 'changed'}
          }
        ])).connection!.outgoing,
        isEmpty);
    expect(
        status(snapshot('operator', outgoing: [
          {...secure, 'phase': 'ended'}
        ])).connection!.outgoing,
        isEmpty);
    expect(
        status(snapshot('operator', outgoing: [
          {...secure, 'encrypted': false}
        ])).connection!.outgoing,
        isEmpty);
    final wrong = status(snapshot('operator', outgoing: [
      session('operator', 'verification_failed', identity: 'failed')
    ]));
    expect(wrong.label, 'Karşı cihaz kimliği doğrulanamadı');
    expect(wrong.connection!.insecure, true);
    final compat = status(snapshot('operator', outgoing: [
      session('operator', 'authorization_pending',
          encrypted: false, direct: true, identity: 'unknown')
    ]));
    expect(compat.label, 'Oturum şifrelemesi doğrulanamadı');
    final mixed = status(snapshot('operator',
        outgoing: [secure, session('operator', 'requesting')]));
    expect(mixed.connection!.outgoing[1]['encrypted'], isNull);
    expect(status(snapshot('operator')).connection!.outgoing,
        isEmpty); // fresh authoritative snapshot after close/reopen
    for (final auth in ['password', 'local_consent']) {
      final incoming = status(snapshot('customer', incoming: [
        {'encrypted': true, 'reference': 'incoming-fixture'}
      ]));
      expect(incoming.label, 'Yetkili destek oturumu var', reason: auth);
      expect(incoming.detail, contains('kurumsal kimliği'));
    }
  });
  final states = <String, FilServerStatus>{
    'operator-idle': status(snapshot('operator')),
    'customer-ready': status(snapshot('customer', registration: true)),
    'requesting': status(
        snapshot('operator', outgoing: [session('operator', 'requesting')])),
    'approval-pending': status(snapshot('operator', outgoing: [
      session('operator', 'authorization_pending',
          encrypted: true, direct: true, identity: 'pinned_root_peer_signature')
    ])),
    'video-waiting': status(snapshot('operator', outgoing: [
      session('operator', 'authorized_waiting_video',
          encrypted: true,
          direct: false,
          identity: 'pinned_root_peer_signature')
    ])),
    'video-packet': status(snapshot('operator', outgoing: [
      session('operator', 'video_packet_received',
          encrypted: true,
          direct: false,
          identity: 'pinned_root_peer_signature')
    ])),
    'customer-authorized': status(snapshot('customer', incoming: [
      {'encrypted': true, 'reference': 'incoming-fixture'}
    ])),
    'identity-failed': status(snapshot('operator', outgoing: [
      session('operator', 'verification_failed', identity: 'failed')
    ])),
    'closed': status(snapshot('operator')),
  };
  for (final entry in states.entries) {
    testWidgets('status screenshot ${entry.key} narrow scaled', (tester) async {
      await tester.binding.setSurfaceSize(const Size(320, 620));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(MaterialApp(
          home: MediaQuery(
              data: const MediaQueryData(textScaler: TextScaler.linear(1.5)),
              child: Scaffold(
                  body: RepaintBoundary(
                      key: const ValueKey('status-shot'),
                      child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: ColoredBox(
                              color: Colors.white,
                              child: FilServerStatusIndicator(
                                  status: entry.value))))))));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await expectLater(find.byKey(const ValueKey('status-shot')),
          matchesGoldenFile('goldens/fil-status-${entry.key}.png'));
      await tester.tap(find.text('Bağlantı ayrıntıları'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }
  test(
      'native serialization boundary fixture is consumed without inferred identity',
      () {
    final path = Platform.environment['FIL_STATUS_FIXTURES'] ??
        'test/fixtures/fil_native_status.json';
    final fixtures = jsonDecode(File(path).readAsStringSync()) as List;
    for (final raw in fixtures) {
      final parsed = FilConnectionEvidence.parse(raw);
      expect(parsed, isNotNull);
      expect(parsed!.context, raw['context']);
      expect(parsed.outgoing.length, (raw['outgoing'] as List).length);
    }
  });
}
