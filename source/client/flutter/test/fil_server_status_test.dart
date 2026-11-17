import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_hbb/desktop/widgets/fil_server_status.dart';

Map<String, dynamic> observation(String state, {int age = 0}) => {
      'version': 1,
      'scope': 'unsigned_nat_service_only',
      'identity_verified': false,
      'state': state,
      'available': state == 'available_unverified',
      'reason':
          state == 'available_unverified' ? 'unsigned_nat_response' : 'timeout',
      'checked_ago_ms': age,
    };

void main() {
  test(
      'Unsigned availability never becomes authenticated readiness; stale and forged data fail closed',
      () {
    final available =
        FilServerStatus.fromNative(observation('available_unverified'));
    expect(available.state, 'available_unverified');
    expect(available.label, equals('Destek hazırlığı tamamlanamadı'));
    for (final bad in [
      null,
      {},
      observation('ready'),
      {...observation('available_unverified'), 'identity_verified': true},
      observation('available_unverified', age: 15001),
      {...observation('available_unverified'), 'checked_ago_ms': -1},
      {...observation('available_unverified'), 'available': false},
      {...observation('available_unverified'), 'scope': 'session_authenticated'}
    ]) {
      expect(FilServerStatus.fromNative(bad).state, 'identity_unavailable');
    }
    for (final state in ['connecting', 'reconnecting', 'disconnected']) {
      expect(FilServerStatus.fromNative(observation(state)).state, state);
    }
  });

  testWidgets(
      'Both profiles can display narrow, scaled truthful text and accessible scope without Ready',
      (tester) async {
    tester.view.physicalSize = const Size(320, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final semantics = tester.ensureSemantics();

    for (final brightness in [Brightness.light, Brightness.dark]) {
      await tester.pumpWidget(MaterialApp(
          theme: ThemeData(brightness: brightness),
          home: Scaffold(
              body: MediaQuery(
                  data:
                      const MediaQueryData(textScaler: TextScaler.linear(1.5)),
                  child: const SizedBox(
                      width: 260,
                      child: FilServerStatusIndicator(
                          status: FilServerStatus('available_unverified')))))));
      expect(find.text('Destek hazırlığı tamamlanamadı'),
          findsOneWidget);
      expect(find.textContaining('Ready'), findsNothing);
      expect(
          find.bySemanticsLabel(
              RegExp('Destek hazırlığı tamamlanamadı.*NAT yanıtı')),
          findsOneWidget);
      expect(tester.takeException(), isNull);
    }
    await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
            body: SizedBox(
                width: 260,
                child: FilServerStatusIndicator(
                    status: FilServerStatus('available_unverified'),
                    serviceStopped: true)))));
    expect(find.text('Yerel destek hizmeti çalışmıyor'), findsOneWidget);
    expect(tester.takeException(), isNull);
    semantics.dispose();
  });
  testWidgets(
      'Local lease expires; hung reads are single-flight and late/disposed results cannot revive status',
      (tester) async {
    final seen = <String>[];
    var calls = 0;
    var next = Future<dynamic>.value(
        {'fil_server_status': observation('available_unverified', age: 14000)});
    final poller = FilServerStatusPoller(
      read: () {
        calls++;
        return next;
      },
      onStatus: (status) => seen.add(status.state),
      timeout: const Duration(seconds: 2),
    );
    await poller.poll();
    expect(seen.last, 'available_unverified');
    final stalled = Completer<dynamic>();
    next = stalled.future;
    final pending = poller.poll();
    // The previous sample must expire even while the next bridge call stalls.
    await tester.pump(const Duration(milliseconds: 1100));
    expect(seen.last, 'identity_unavailable');
    await tester.pump(const Duration(milliseconds: 1000));
    await pending;
    expect(seen.last, 'identity_unavailable');
    await poller.poll();
    expect(calls, 2); // One unresolved bridge read, no retry accumulation.
    final beforeLate = seen.length;
    stalled
        .complete({'fil_server_status': observation('available_unverified')});
    await tester.pump();
    expect(seen.length, beforeLate);
    final disposedRead = Completer<dynamic>();
    next = disposedRead.future;
    final pendingDispose = poller.poll();
    poller.dispose();
    disposedRead
        .complete({'fil_server_status': observation('available_unverified')});
    await tester.pump();
    await pendingDispose;
    expect(seen.length, beforeLate);
  });
}
