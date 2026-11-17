import 'dart:async';
import 'package:flutter/material.dart';
import '../../models/fil_operator_updates.dart';

class FilOperatorUpdateCenter extends StatefulWidget {
  final FilOperatorUpdateController controller;
  final bool isOperator;
  final Future<void> Function(Uri) openInformation;
  const FilOperatorUpdateCenter(
      {super.key,
      required this.controller,
      required this.openInformation,
      required this.isOperator});
  @override
  State<FilOperatorUpdateCenter> createState() =>
      _FilOperatorUpdateCenterState();
}

class _FilOperatorUpdateCenterState extends State<FilOperatorUpdateCenter> {
  Timer? _timer;
  @override
  void initState() {
    super.initState();
    if (!widget.isOperator) return;
    widget.controller.restore();
    // Neither startup nor support is awaited on metadata availability.
    Future.microtask(() => widget.controller.check());
    _timer = Timer.periodic(
        const Duration(minutes: 15), (_) => widget.controller.check());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => !widget.isOperator
      ? const SizedBox.shrink()
      : AnimatedBuilder(
          animation: widget.controller,
          builder: (_, __) => TextButton.icon(
                icon: const Icon(Icons.info_outline, size: 14),
                label: Text(widget.controller.label,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 12)),
                onPressed: () => _show(context),
              ));
  Future<void> _open(BuildContext context, Uri uri) async {
    try {
      await widget.openInformation(uri);
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.maybeOf(context)?.showSnackBar(const SnackBar(
            content: Text('Bağlantı açılamadı. Daha sonra yeniden deneyin.')));
      }
    }
  }

  void _show(BuildContext context) {
    showDialog<void>(
        context: context,
        builder: (dialogContext) => AnimatedBuilder(
              animation: widget.controller,
              builder: (_, __) {
                final c = widget.controller, m = c.manifest;
                return AlertDialog(
                  title: const Text('Güncelleme bilgileri'),
                  content: SizedBox(
                      width: 440,
                      child: SingleChildScrollView(
                          child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Text('FilDesk',
                              style: TextStyle(fontWeight: FontWeight.bold)),
                          Text('Yüklü sürüm: ${c.installed.text} · Operator'),
                          Text(c.label),
                          if (m != null) ...[
                            Text(
                                'Son bilinen onaylı sürüm: ${m.latest.text}${c.fresh ? '' : ' (eski bilgi)'}'),
                            Text(
                                'Yayın tarihi: ${m.published.toIso8601String()}'),
                            Text(m.notes),
                            if (m.minimum.compareTo(c.installed) > 0)
                              const Text(
                                  'Bu sürüm için güncelleme gerekli. Destek bağlantınız otomatik kesilmez.'),
                            if (c.fresh && !c.failed)
                              TextButton(
                                  onPressed: () =>
                                      _open(dialogContext, m.infoUrl),
                                  child: const Text('Onaylı sürüm bilgileri')),
                          ],
                          const Text(
                              'Operator paketi özel dağıtılır; otomatik indirme veya kurulum yapılmaz.'),
                          const Divider(),
                          const Text('RustDesk kaynak projesi',
                              style: TextStyle(fontWeight: FontWeight.bold)),
                          Text(
                              'Kayıtlı kaynak tabanı: ${m?.baseTag ?? 'bilinmiyor'}'),
                          if (m?.baseCommit != null)
                            SelectableText('Taban commit: ${m!.baseCommit}'),
                          Text(
                              'Son bilinen kararlı sürüm: ${m?.upstreamVersion ?? 'bilinmiyor'}'),
                          if (m?.upstreamPublished != null)
                            Text(
                                'Yayın tarihi: ${m!.upstreamPublished!.toIso8601String()}'),
                          const Text(
                              'Kaynak güncellemeleri uyumluluk testinden sonra FilDesk’e alınır. Yeni RustDesk sürümü bir FilDesk güncellemesi değildir.'),
                          TextButton(
                              onPressed: () => _open(
                                  dialogContext,
                                  Uri.parse(
                                      'https://github.com/rustdesk/rustdesk/releases')),
                              child: const Text('Resmî RustDesk sürümleri')),
                          const Divider(),
                          const Text('Güvenlik',
                              style: TextStyle(fontWeight: FontWeight.bold)),
                          if (m == null || m.advisories.isEmpty)
                            const Text(
                                'İlgili güvenlik bildirimi bilgisi yok. Bu, açık bulunmadığı anlamına gelmez.'),
                          for (final a
                              in m?.advisories ?? <Map<String, String>>[])
                            TextButton(
                                onPressed: () =>
                                    _open(dialogContext, Uri.parse(a['url']!)),
                                child: Text(
                                    '${a['id']} · ${_priority(a['priority']!)} · ${_review(a['status']!)}')),
                          Text(
                              'Son başarılı kontrol: ${c.lastSuccess?.toUtc().toIso8601String() ?? 'henüz yok'}'),
                          const Text(
                              'Bilgiler HTTPS üzerinden alınır; imzalı yayın doğrulaması veya güvenlik sertifikası değildir.'),
                        ],
                      ))),
                  actions: [
                    TextButton(
                        onPressed: c.busy ? null : () => c.check(manual: true),
                        child: const Text('Yeniden kontrol et')),
                    TextButton(
                        onPressed: () => Navigator.pop(dialogContext),
                        child: const Text('Kapat')),
                  ],
                );
              },
            ));
  }
}

String _priority(String v) => const {
      'unknown': 'bilinmiyor',
      'low': 'düşük',
      'moderate': 'orta',
      'high': 'yüksek',
      'critical': 'kritik'
    }[v]!;
String _review(String v) => const {
      'review_required': 'inceleme gerekli',
      'reviewed_not_affected': 'incelendi, etkilenmiyor',
      'fix_pending': 'düzeltme bekleniyor'
    }[v]!;
