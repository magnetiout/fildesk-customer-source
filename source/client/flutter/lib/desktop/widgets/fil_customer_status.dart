import 'package:flutter/material.dart';
import 'fil_server_status.dart';

String filCustomerConnectionLabel(FilServerStatus s) {
  if (s.state == 'identity_failed' || s.connection?.insecure == true) return 'Bağlantı güvenliği doğrulanamadı';
  if (s.connection?.incoming.isNotEmpty == true) return 'Destek oturumu açık';
  if ((s.connection?.service?['pending_approval'] as int? ?? 0) > 0) return 'Bağlantı onayınız bekleniyor';
  if (s.connection?.registered == true) return 'Uzaktan destek için hazır';
  if (s.state == 'connecting' || s.state == 'reconnecting') return 'Bağlantı kontrol ediliyor…';
  if (s.state == 'available_unverified') return 'Destek hazırlığı tamamlanamadı';
  return 'Bağlantı kurulamadı';
}
String filElevationLabel(String? phase) => const {
  'requested':'Yönetici izni hazırlanıyor',
  'waiting_local_approval':'Yönetici izniniz bekleniyor',
  'helper_starting':'Yönetici işlevleri hazırlanıyor',
  'active':'Yönetici yetkisi etkin',
  'declined':'Yönetici izni verilmedi. Standart yetkilerle çalışıyor.',
  'cancelled':'Yönetici izni iptal edildi. Standart yetkilerle çalışıyor.',
  'timed_out':'Yönetici izni zamanında tamamlanamadı. Standart yetkilerle çalışıyor.',
  'failed':'Yönetici işlevleri başlatılamadı. Standart yetkilerle çalışıyor.',
}[phase] ?? 'Standart yetkilerle çalışıyor. Yönetici işlemleri için ek izin gerekir.';

class FilCustomerStatusPanel extends StatelessWidget {
  final FilServerStatus status;
  final Map elevation;
  final VoidCallback retryConnection, requestElevation, cancelElevation, exportDiagnostic;
  const FilCustomerStatusPanel({super.key,required this.status,required this.elevation,required this.retryConnection,required this.requestElevation,required this.cancelElevation,required this.exportDiagnostic});
  @override Widget build(BuildContext context) {
    final phase=elevation['phase'] is String ? elevation['phase'] as String : null;
    final pending=['requested','waiting_local_approval','helper_starting'].contains(phase);
    // Only the authenticated helper ping/pong enables this capability assertion.
    final safePhase=phase=='active' && elevation['helper_authenticated']!=true ? 'failed' : phase;
    return Column(crossAxisAlignment:CrossAxisAlignment.start,mainAxisSize:MainAxisSize.min,children:[
      Text(filCustomerConnectionLabel(status),style:const TextStyle(fontSize:14)),
      const SizedBox(height:6),Text(safePhase=='failed' && elevation['process_elevated']==true ? 'Yönetici izni var; destek yardımcısı başlatılamadı.' : filElevationLabel(safePhase),style:const TextStyle(fontSize:12)),
      Wrap(spacing:8,children:[
        if(safePhase!='active') TextButton(onPressed:pending?cancelElevation:requestElevation,child:Text(pending?'İzin isteğini iptal et':'Yönetici izni iste')),
        if(status.connection?.registered!=true && status.connection?.incoming.isNotEmpty!=true) TextButton(onPressed:retryConnection,child:const Text('Bağlantıyı yeniden kontrol et')),
        TextButton(onPressed:exportDiagnostic,child:const Text('Tanı kaydını dışa aktar')),
      ]),
    ]);
  }
}
