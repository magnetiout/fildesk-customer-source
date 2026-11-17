import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_hbb/desktop/widgets/fil_customer_status.dart';
import 'package:flutter_hbb/desktop/widgets/fil_server_status.dart';

void main() {
 test('NAT alone is not readiness; requested elevation is not active capability',(){
  expect(filCustomerConnectionLabel(const FilServerStatus('available_unverified')),'Destek hazırlığı tamamlanamadı');
  expect(filCustomerConnectionLabel(FilServerStatus.connecting),'Bağlantı kontrol ediliyor…');
  expect(filCustomerConnectionLabel(const FilServerStatus('identity_failed')),'Bağlantı güvenliği doğrulanamadı');
  expect(filElevationLabel('waiting_local_approval'),'Yönetici izniniz bekleniyor');
 });
 testWidgets('Customer small/large DPI keeps controls, removes technical details and requires authenticated ACK', (tester) async {
  var retry=0, request=0,cancel=0,exports=0;
  for(final scale in [1.0,1.5,2.0]) {
   tester.view.physicalSize=const Size(360,900);tester.view.devicePixelRatio=1;
   await tester.pumpWidget(MaterialApp(home:Scaffold(body:MediaQuery(data:MediaQueryData(textScaler:TextScaler.linear(scale)),child:SingleChildScrollView(child:FilCustomerStatusPanel(
    status:const FilServerStatus('available_unverified'),elevation:const {'phase':'active','helper_authenticated':false},
    retryConnection:(){retry++;},requestElevation:(){request++;},cancelElevation:(){cancel++;},exportDiagnostic:(){exports++;},
   ))))));
   expect(find.text('Yönetici yetkisi etkin'),findsNothing);
   expect(find.textContaining('Sunucuya erişiliyor'),findsNothing);
   expect(find.textContaining('Bağlantı ayrıntıları'),findsNothing);
   expect(find.textContaining('NAT'),findsNothing);
   expect(find.textContaining('available_unverified'),findsNothing);
   await tester.tap(find.text('Yönetici izni iste'));await tester.tap(find.text('Tanı kaydını dışa aktar'));
   expect(tester.takeException(),isNull);
  }
  expect(request,3);expect(exports,3);expect(cancel,0);expect(retry,0);
  tester.view.resetPhysicalSize();tester.view.resetDevicePixelRatio();
 });
}
