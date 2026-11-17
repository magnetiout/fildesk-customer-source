import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_hbb/models/fil_operator_updates.dart';
import 'package:flutter_hbb/desktop/widgets/fil_operator_update_center.dart';

final now = DateTime.utc(2026, 10, 26, 8);
Map<String, dynamic> metadata() => {
      'schema': 1,
      'product': 'FilDesk',
      'role': 'operator',
      'approved': true,
      'latest': '1.5.0+74',
      'minimum': '1.5.0+73',
      'notes': 'Özel dağıtım; bilgi amaçlı.',
      'generated_at': now.toIso8601String(),
      'expires_at': now.add(const Duration(hours: 48)).toIso8601String(),
      'published_at': now.subtract(const Duration(days: 1)).toIso8601String(),
      'information_url':
          'https://filteknoloji.com/uzak-destek/operator-surumleri/1.5.0-74',
      'upstream_base': {
        'tag': '1.5.0',
        'commit': FilOperatorUpdateController.recordedUpstreamCommit
      },
      'upstream': {
        'version': '1.5.0',
        'prerelease': false,
        'draft': false,
        'published_at': now.subtract(const Duration(days: 2)).toIso8601String(),
        'url': 'https://github.com/rustdesk/rustdesk/releases/tag/1.5.0'
      },
      'advisories': [],
    };
FilOperatorUpdateController controller(
        {UpdateRead? fetch,
        bool Function()? active,
        String cache = '',
        DateTime Function()? clock}) =>
    FilOperatorUpdateController(
        installed: '1.5.0+74',
        fetch: fetch ?? () async => jsonEncode(metadata()),
        readCache: () => cache,
        writeCache: (_) async {},
        sessionActive: active ?? () => false,
        clock: clock ?? () => now);
void main() {
  test('Stable approved version, distinct upstream channel and minimum policy',
      () async {
    final c = controller();
    expect(c.label, contains('henüz alınamadı'));
    await c.check();
    expect(c.label, 'FilDesk 1.5.0+74 · Güncel');
    final newer = metadata()
      ..['latest'] = '1.5.0+75'
      ..['minimum'] = '1.5.0+75';
    final n = controller(fetch: () async => jsonEncode(newer));
    await n.check();
    expect(n.label, 'FilDesk güncellemesi mevcut');
    expect(n.manifest!.minimum.compareTo(n.installed), greaterThan(0));
    final upstream = metadata();
    upstream['upstream'] = {
      'version': '1.6.0',
      'prerelease': false,
      'draft': false,
      'published_at': now.toIso8601String(),
      'url': 'https://github.com/rustdesk/rustdesk/releases/tag/1.6.0'
    };
    final u = controller(fetch: () async => jsonEncode(upstream));
    await u.check();
    expect(u.label, 'RustDesk kaynak projesinde yeni sürüm');
    expect(u.manifest!.latest.text, '1.5.0+74');
    for (final bad in [
      'v1.5.0',
      '1.5',
      '1.5.0-beta',
      '01.5.0',
      '1.5.0+9999999'
    ]) {
      expect(() => FilVersion.parse(bad), throwsFormatException);
    }
  });
  test('Malformed, role, stale, URL, trust-base and prerelease boundaries',
      () async {
    for (final change in <Map<String, dynamic>>[
      {'role': 'customer'},
      {'approved': false},
      {'latest': 'broken'},
      {'download_url': 'https://filteknoloji.com/downloads/operator.exe'},
      {
        'information_url':
            'https://evil.example/uzak-destek/operator-surumleri/74'
      },
      {
        'information_url':
            'https://filteknoloji.com:443/uzak-destek/operator-surumleri/74'
      },
      {
        'information_url':
            'https://filteknoloji.com/uzak-destek/operator-surumleri/74?redirect=evil'
      },
      {
        'information_url':
            'https://filteknoloji.com/uzak-destek/operator-surumleri/../74'
      },
      {
        'expires_at': now.subtract(const Duration(seconds: 1)).toIso8601String()
      },
      {'minimum': '9.0.0'},
      {
        'upstream_base': {'commit': '0' * 40, 'tag': '1.5.0'}
      },
      {
        'upstream': {
          'version': '1.6.0',
          'prerelease': false,
          'draft': false,
          'published_at': now.toIso8601String(),
          'url': 'https://github.com/other/rustdesk/releases/tag/1.6.0'
        }
      },
      {
        'advisories': [
          {
            'id': 'GHSA-1234-1234-1234',
            'url': 'https://evil.example',
            'status': 'review_required',
            'priority': 'high'
          }
        ]
      },
    ]) {
      final c =
          controller(fetch: () async => jsonEncode({...metadata(), ...change}));
      await c.check();
      expect(c.label, contains('henüz alınamadı'));
      expect(c.manifest, isNull);
    }
    for (final raw in ['not-json', '[]', 'x' * 65537]) {
      final c = controller(fetch: () async => raw);
      await c.check();
      expect(c.failed, isTrue);
    }
    final pre = metadata();
    pre['upstream'] = {
      'version': '1.6.0-beta',
      'prerelease': true,
      'draft': false
    };
    final p = controller(fetch: () async => jsonEncode(pre));
    await p.check();
    expect(p.manifest!.upstreamVersion, isNull);
    final missing = metadata()..remove('upstream_base');
    final m = controller(fetch: () async => jsonEncode(missing));
    await m.check();
    expect(m.label, contains('karşılaştırması gerekli'));
  });
  test(
      '24h cache, network error, backoff, active session and disposal are safe',
      () async {
    var calls = 0, active = true;
    var time = now;
    String saved = '';
    final c = FilOperatorUpdateController(
        installed: '1.5.0+74',
        fetch: () async {
          calls++;
          return jsonEncode(metadata());
        },
        readCache: () => saved,
        writeCache: (v) async {
          saved = v;
        },
        sessionActive: () => active,
        clock: () => time);
    await c.check();
    expect(calls, 0);
    active = false;
    await c.check();
    await c.check();
    expect(calls, 1);
    final r = controller(cache: saved);
    r.restore();
    expect(r.label, contains('Güncel'));
    time = time.add(const Duration(hours: 25));
    expect(c.label, contains('henüz alınamadı'));
    final stale = controller(
        cache: saved, clock: () => now.add(const Duration(hours: 49)));
    stale.restore();
    expect(stale.fresh, isFalse);
    var errors = 0;
    final f = controller(fetch: () async {
      errors++;
      throw Exception('http failure');
    });
    await f.check();
    await f.check();
    await f.check(manual: true);
    expect(errors, 1);
    expect(f.failed, isTrue);
    final cachedFailure =
        controller(cache: saved, fetch: () async => throw Exception('HTTP404'));
    cachedFailure.restore();
    await cachedFailure.check(manual: true);
    expect(cachedFailure.manifest, isNotNull);
    expect(cachedFailure.label, contains('henüz alınamadı'));
    final completer = Completer<String>();
    final disposed = controller(fetch: () => completer.future);
    final done = disposed.check();
    disposed.dispose();
    completer.complete(jsonEncode(metadata()));
    await done;
    expect(disposed.manifest, isNull);
  });
  testWidgets('Customer never displays or starts Operator updates',
      (tester) async {
    var calls = 0;
    final c = controller(fetch: () async {
      calls++;
      return jsonEncode(metadata());
    });
    await tester.pumpWidget(MaterialApp(
        home: FilOperatorUpdateCenter(
            isOperator: false, controller: c, openInformation: (_) async {})));
    await tester.pumpAndSettle();
    expect(calls, 0);
    expect(find.byType(TextButton), findsNothing);
    await tester.pumpWidget(const SizedBox());
    c.dispose();
  });
  testWidgets(
      'Timeout is bounded and small scaled Operator footer/dialog stays usable',
      (tester) async {
    final timeout = controller(fetch: () => Completer<String>().future);
    final pending = timeout.check();
    await tester.pump(const Duration(seconds: 10));
    await pending;
    expect(timeout.failed, isTrue);
    tester.view.physicalSize = const Size(360, 740);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final c = controller();
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: MediaQuery(
                data: const MediaQueryData(textScaler: TextScaler.linear(1.5)),
                child: Align(
                    alignment: Alignment.bottomCenter,
                    child: SizedBox(
                        width: 320,
                        child: FilOperatorUpdateCenter(
                            isOperator: true,
                            controller: c,
                            openInformation: (_) async {})))))));
    await tester.pumpAndSettle();
    await tester.tap(find.text('FilDesk 1.5.0+74 · Güncel'));
    await tester.pumpAndSettle();
    expect(find.text('Güncelleme bilgileri'), findsOneWidget);
    expect(find.text('RustDesk kaynak projesi'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('Kapat'));
    await tester.pumpAndSettle();
    await tester.pumpWidget(const SizedBox());
    c.dispose();
    timeout.dispose();
  });
}
