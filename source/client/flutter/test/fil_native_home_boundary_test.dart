import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_hbb/desktop/widgets/fil_server_status.dart';

void main() {
  final native = jsonDecode(
      File('test/fixtures/fil_native_status.json').readAsStringSync()) as List;
  Map payload(int index, {String nat = 'available_unverified'}) => {
        'fil_server_status': {
          'version': 1,
          'scope': 'unsigned_nat_service_only',
          'identity_verified': false,
          'state': nat,
          'available': nat == 'available_unverified',
          'reason': nat == 'available_unverified'
              ? 'unsigned_nat_response'
              : 'timeout',
          'checked_ago_ms': 0
        },
        'fil_connection_status': native[index],
      };
  testWidgets(
      'actual native serializer to poller to label; NAT cannot erase authorization; close/reopen uses authoritative snapshot',
      (tester) async {
    dynamic current = payload(2);
    final seen = <FilServerStatus>[];
    var poller =
        FilServerStatusPoller(read: () async => current, onStatus: seen.add);
    await poller.poll();
    expect(seen.last.label, 'Oturum yetkili · görüntü bekleniyor');
    current = payload(2, nat: 'disconnected');
    await poller.poll();
    expect(seen.last.label, 'Oturum yetkili · görüntü bekleniyor');
    poller.dispose();
    poller =
        FilServerStatusPoller(read: () async => current, onStatus: seen.add);
    await poller.poll();
    expect(seen.last.connection!.outgoing.length, 1);
    current = payload(4);
    await poller.poll();
    expect(seen.last.connection!.outgoing, isEmpty);
    current = {'fil_server_status': payload(0)['fil_server_status']};
    await poller.poll();
    expect(seen.last.connection, isNull);
    expect(seen.last.label, 'Destek hazırlığı tamamlanamadı');
    poller.dispose();
  });
  testWidgets(
      'late native snapshot after timeout cannot revive prior session evidence',
      (tester) async {
    final seen = <FilServerStatus>[];
    dynamic current = Future.value(payload(3));
    final poller = FilServerStatusPoller(
        read: () => current,
        onStatus: seen.add,
        timeout: const Duration(seconds: 1));
    await poller.poll();
    expect(seen.last.connection!.outgoing.length, 1);
    final late = Completer<dynamic>();
    current = late.future;
    final pending = poller.poll();
    await tester.pump(const Duration(seconds: 1));
    await pending;
    expect(seen.last.connection, isNull);
    final count = seen.length;
    late.complete(payload(3));
    await tester.pump();
    expect(seen.length, count);
    expect(seen.last.connection, isNull);
    poller.dispose();
  });
}
