import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_hbb/desktop/widgets/fildesk_support.dart';

// Rasterization differs between Flutter's Linux and Windows test engines.
// Keep the original references; Windows owns separately reviewed baselines.
String goldenPath(String name) => Platform.isWindows
    ? 'goldens/windows/$name'
    : 'goldens/$name';

Future<void> main() async {
  TestWidgetsFlutterBinding.ensureInitialized();
  final sdk = Platform.environment['FIL_FLUTTER_ROOT'] ?? Platform.environment['FLUTTER_ROOT'];
  if (sdk == null) throw StateError('Pinned Flutter SDK path required for deterministic fonts');
  final font = FontLoader('Roboto');
  for (final weight in ['Regular', 'Medium', 'Bold']) {
    font.addFont(File('$sdk/bin/cache/artifacts/material_fonts/Roboto-$weight.ttf')
        .readAsBytes().then((bytes) => ByteData.sublistView(bytes)));
  }
  await font.load();
  final icons = FontLoader('MaterialIcons');
  icons.addFont(File('$sdk/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf')
      .readAsBytes().then((bytes) => ByteData.sublistView(bytes)));
  await icons.load();
  for (final brightness in [Brightness.light, Brightness.dark]) {
  for (final width in [360.0, 440.0]) {
    testWidgets('customer layout and controls at width $width ${brightness.name}', (tester) async {
      await tester.binding.setSurfaceSize(Size(width, 620));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final id = TextEditingController(text: '123 456 789');
      final password = TextEditingController(text: 'TEST-only7');
      addTearDown(id.dispose);
      addTearDown(password.dispose);
      var refresh = 0, settings = 0, general = 0;
      String? copied;
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
        if (call.method == 'Clipboard.setData') copied = call.arguments['text'];
        return null;
      });
      addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, null));
      await tester.pumpWidget(MaterialApp(theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF205C74), brightness: brightness)), home: RepaintBoundary(
        key: const Key('support'), child: Scaffold(body: FilDeskSupport(id: id, password: password,
          temporaryEnabled: true, onRefresh: () => refresh++, onSettings: () => settings++,
          onGeneral: () => general++)))));
      await tester.runAsync(() => precacheImage(AssetImage(brightness == Brightness.dark ? 'assets/logo_dark.png' : 'assets/logo.png'),
        tester.element(find.byType(FilDeskBrand))));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('FilDesk'), findsOneWidget);
      expect(tester.getSize(find.byType(FilDeskLogo)), const Size(50, 50));
      expect(find.byIcon(Icons.support_agent), findsNothing);
      expect(find.textContaining('FilDesk-Dev'), findsNothing);
      await expectLater(find.byKey(const Key('support')),
        matchesGoldenFile(goldenPath('fildesk-customer-${width.toInt()}${brightness == Brightness.dark ? '-dark' : ''}.png')));
      await tester.tap(find.byTooltip('ID’yi kopyala'));
      expect(copied, id.text);
      await tester.tap(find.byTooltip('Parolayı kopyala'));
      expect(copied, password.text);
      await tester.tap(find.byTooltip('Parolayı yenile'));
      await tester.tap(find.text('Parola ve izinler'));
      await tester.tap(find.text('Ayarlar'));
      expect([refresh, settings, general], [1, 1, 1]);
    });
  }
  }
  for (final brightness in [Brightness.light, Brightness.dark]) {
  testWidgets('operator identity ${brightness.name} has no customer credential card', (tester) async {
    await tester.binding.setSurfaceSize(const Size(440, 140));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(MaterialApp(theme: ThemeData(brightness: brightness), home: const RepaintBoundary(
      key: Key('operator'), child: Scaffold(body: Column(children: [FilDeskBrand(operatorProfile: true)])))));
    await tester.runAsync(() => precacheImage(AssetImage(brightness == Brightness.dark ? 'assets/logo_dark.png' : 'assets/logo.png'),
      tester.element(find.byType(FilDeskBrand))));
    await tester.pumpAndSettle();
    expect(find.text('Fil Teknoloji · Operatör'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
    await expectLater(find.byKey(const Key('operator')), matchesGoldenFile(goldenPath('fildesk-operator${brightness == Brightness.dark ? '-dark' : ''}.png')));
  });
  }
  for (final brightness in [Brightness.light, Brightness.dark]) {
    testWidgets('operator recent empty state wraps at narrow and wide widths ${brightness.name}', (tester) async {
      addTearDown(() => tester.binding.setSurfaceSize(null));
      for (final width in [320.0, 720.0]) {
        await tester.binding.setSurfaceSize(Size(width, 320));
        await tester.pumpWidget(MaterialApp(theme: ThemeData(brightness: brightness),
          home: const RepaintBoundary(key: Key('recent-empty'),
            child: Scaffold(body: FilDeskRecentEmpty()))));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        expect(find.text('Henüz bağlantı geçmişi yok.'), findsOneWidget);
        expect(find.text("Uzaktan destek başlatmak için yukarıya müşteri ID'sini girin."), findsOneWidget);
        expect(find.byIcon(Icons.desktop_windows_outlined), findsOneWidget);
        expect(find.byIcon(Icons.sentiment_very_dissatisfied_rounded), findsNothing);
        await expectLater(find.byKey(const Key('recent-empty')),
          matchesGoldenFile(goldenPath('fildesk-recent-empty-${width.toInt()}-${brightness.name}.png')));
      }
    });
  }

}
