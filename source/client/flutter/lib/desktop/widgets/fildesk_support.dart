import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Identical official geometry; a documented green tint improves dark contrast.
class FilDeskLogo extends StatelessWidget {
  final double size;
  const FilDeskLogo({super.key, this.size = 50});

  @override
  Widget build(BuildContext context) => Image.asset(
    Theme.of(context).brightness == Brightness.dark
        ? 'assets/logo_dark.png' : 'assets/logo.png',
    width: size, height: size, semanticLabel: 'Fil Teknoloji logosu');
}

/// Official Fil Teknoloji mark, shared with the native EXE and tray resources.
class FilDeskBrand extends StatelessWidget {
  final bool operatorProfile;
  const FilDeskBrand({super.key, this.operatorProfile = false});

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 24),
    child: Row(children: [
      const FilDeskLogo(),
      const SizedBox(width: 14),
      Expanded(child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('FilDesk', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w600)),
          Text(operatorProfile ? 'Fil Teknoloji · Operatör' : 'Fil Teknoloji',
            style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.onSurfaceVariant)),
        ])),
    ]),
  );
}

/// Presentation only. Credentials, permissions and refresh remain upstream-owned.
class FilDeskSupport extends StatelessWidget {
  final TextEditingController id;
  final TextEditingController password;
  final bool temporaryEnabled;
  final VoidCallback onRefresh;
  final VoidCallback onSettings;
  final VoidCallback onGeneral;
  const FilDeskSupport({super.key, required this.id, required this.password,
    required this.temporaryEnabled, required this.onRefresh,
    required this.onSettings, required this.onGeneral});

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const FilDeskBrand(),
      Padding(padding: const EdgeInsets.symmetric(horizontal: 24),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('Uzaktan destek', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          const Text('ID ve parolanızı yalnız yetkili destek personeliyle paylaşın.',
            style: TextStyle(fontSize: 14, height: 1.4)),
          const SizedBox(height: 24),
          _credential(context, "Bu bilgisayarın ID’si", id, 'ID’yi kopyala', true),
          const SizedBox(height: 16),
          _credential(context, 'Geçici parola', password, 'Parolayı kopyala', temporaryEnabled,
            refresh: temporaryEnabled),
          const SizedBox(height: 18),
          Wrap(spacing: 8, runSpacing: 4, children: [
            TextButton.icon(onPressed: onSettings, icon: const Icon(Icons.tune, size: 18),
              label: const Text('Parola ve izinler')),
            TextButton.icon(onPressed: onGeneral, icon: const Icon(Icons.settings_outlined, size: 18),
              label: const Text('Ayarlar')),
          ]),
          const SizedBox(height: 12),
        ])),
    ],
  );

  Widget _credential(BuildContext context, String label, TextEditingController controller,
      String copyLabel, bool copyEnabled, {bool refresh = false}) => DecoratedBox(
    decoration: BoxDecoration(
      border: Border.all(color: Theme.of(context).dividerColor),
      borderRadius: BorderRadius.circular(10)),
    child: Padding(padding: const EdgeInsets.fromLTRB(16, 12, 8, 12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: const TextStyle(fontSize: 13)),
        Row(children: [
          Expanded(child: TextField(controller: controller, readOnly: true,
            style: const TextStyle(fontSize: 23, fontWeight: FontWeight.w500),
            decoration: const InputDecoration(border: InputBorder.none, isDense: true))),
          ValueListenableBuilder<TextEditingValue>(valueListenable: controller,
            builder: (context, value, _) => IconButton(tooltip: copyLabel,
              onPressed: copyEnabled && value.text.isNotEmpty ? () async {
                await Clipboard.setData(ClipboardData(text: value.text));
                if (context.mounted) {
                  ScaffoldMessenger.maybeOf(context)?.showSnackBar(
                    const SnackBar(content: Text('Kopyalandı'), duration: Duration(seconds: 2)));
                }
              } : null,
              icon: const Icon(Icons.copy_outlined, size: 20))),
          if (refresh) IconButton(tooltip: 'Parolayı yenile', onPressed: onRefresh,
            icon: const Icon(Icons.refresh, size: 22)),
        ]),
      ])),
  );
}

/// Operator-only empty recent history; peer loading and filtering stay upstream.
class FilDeskRecentEmpty extends StatelessWidget {
  const FilDeskRecentEmpty({super.key});

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.desktop_windows_outlined, size: 40,
          color: Theme.of(context).colorScheme.onSurfaceVariant),
        const SizedBox(height: 12),
        const Text('Henüz bağlantı geçmişi yok.', textAlign: TextAlign.center,
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
        const SizedBox(height: 8),
        Text("Uzaktan destek başlatmak için yukarıya müşteri ID'sini girin.",
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            height: 1.4, color: Theme.of(context).colorScheme.onSurfaceVariant)),
      ]),
    ),
  );
}
