import 'dart:io';
import 'package:flutter/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_hbb/desktop/widgets/fil_cm_authorization_status.dart';
Future<void> main() async {
 TestWidgetsFlutterBinding.ensureInitialized();
 final sdk=Platform.environment['FIL_FLUTTER_ROOT'];
 if(sdk==null)throw StateError('Pinned Flutter SDK required for real font metrics');
 final font=FontLoader('Roboto');
 font.addFont(File('$sdk/bin/cache/artifacts/material_fonts/Roboto-Regular.ttf').readAsBytes().then((bytes)=>ByteData.sublistView(bytes)));
 await font.load();
 const tr = {'Access authorized':'Erişim onaylandı','Awaiting access approval':'Erişim onayı bekleniyor','Time in this window after access approval':'İzin onayından sonra bu pencerede geçen süre','Image status is shown in the operator window.':'Görüntü durumu operatör ekranında gösterilir.','Disconnected':'Bağlantı Kesildi'};
 for (final turkish in [false,true]) {
  for (final width in [128.0,200.0,360.0]) {
   for (final scale in [1.0,1.5]) {
   for (final authorized in [false,true]) {
    for (final disconnected in [false,true]) {
     testWidgets('authorization tr=$turkish width=$width scale=$scale auth=$authorized disconnected=$disconnected',(tester) async {
      await tester.binding.setSurfaceSize(Size(width,400));
      addTearDown(()=>tester.binding.setSurfaceSize(null));
      String translate(String key)=>turkish ? tr[key] ?? key : key;
      await tester.pumpWidget(MaterialApp(home:MediaQuery(data:MediaQueryData(textScaler:TextScaler.linear(scale)),child:Scaffold(body:FilCmAuthorizationStatus(authorized:authorized,disconnected:disconnected,elapsed:'00:12',translate:translate)))));
      expect(tester.takeException(),isNull);
      expect(find.text(translate(disconnected?'Disconnected':authorized?'Access authorized':'Awaiting access approval')),findsOneWidget);
      expect(find.textContaining(translate('Time in this window after access approval')),authorized?findsOneWidget:findsNothing);
      expect(find.text(translate('Image status is shown in the operator window.')),authorized&&!disconnected?findsOneWidget:findsNothing);
      for(final text in ['Connected','Active','Görüntü hazır']) {expect(find.text(text),findsNothing);}
      for(final element in find.byType(Text).evaluate()) {final box=element.renderObject as RenderBox;expect(box.size.width,lessThanOrEqualTo(width));}
     });
    }
   }
   }
  }
 }
 for(final scale in [1.0,1.5,2.0]) {
  for(final turkish in [false,true]) {
   for(final authorized in [false,true]) {
    testWidgets('actual remote layout finite300x462 scale=$scale tr=$turkish auth=$authorized',(tester)async {
     await tester.binding.setSurfaceSize(const Size(300,462));
     addTearDown(()=>tester.binding.setSurfaceSize(null));
     var clicks=0;
     final controlFocus=FocusNode();addTearDown(controlFocus.dispose);
     String translate(String key)=>turkish ? tr[key] ?? key : key;
     await tester.pumpWidget(MaterialApp(home:MediaQuery(data:MediaQueryData(textScaler:TextScaler.linear(scale)),child:Scaffold(body:Padding(
      padding:const EdgeInsets.symmetric(horizontal:8,vertical:4),
      child:FilCmRemoteCardLayout(
       header:Container(margin:const EdgeInsets.symmetric(horizontal:5,vertical:10),padding:const EdgeInsets.all(10),child:Column(children:[
        const SizedBox(height:70,child:Text('Authorized synthetic peer / identity')),
        FilCmAuthorizationStatus(authorized:authorized,disconnected:false,elapsed:'00:12',translate:translate),
       ])),
       permissions:const SizedBox(height:170,child:Align(alignment:Alignment.bottomCenter,child:Text('Last permission row',key:ValueKey('last-permission')))),
       controls:Padding(padding:const EdgeInsets.only(bottom:8),child:Column(mainAxisAlignment:MainAxisAlignment.end,children:[Row(children:[Expanded(child:ElevatedButton(focusNode:controlFocus,key:const ValueKey('consent-or-revoke'),onPressed:()=>clicks++,child:Text(authorized?'Revoke permission':'Accept permission')))])])),
      ),
     )))));
     await tester.pumpAndSettle();
     expect(tester.takeException(),isNull);
     final action=find.byKey(const ValueKey('consent-or-revoke'));
     final before=tester.getRect(action);
     expect(before.bottom,lessThanOrEqualTo(462));expect(before.top,greaterThanOrEqualTo(0));
     await tester.drag(find.byKey(const ValueKey('fil-cm-authorization-scroll')),const Offset(0,-800));
     await tester.pumpAndSettle();
     expect(tester.takeException(),isNull);
     final permission=tester.getRect(find.byKey(const ValueKey('last-permission')));
     expect(permission.bottom,lessThanOrEqualTo(before.top+1));
     expect(tester.getRect(action),before);
     await tester.tap(action);expect(clicks,1);
     for(var i=0;i<8&&!controlFocus.hasFocus;i++) {await tester.sendKeyEvent(LogicalKeyboardKey.tab);await tester.pump();}
     expect(controlFocus.hasFocus,isTrue);
     await tester.sendKeyEvent(LogicalKeyboardKey.enter);await tester.pumpAndSettle();expect(clicks,2);
    });
   }
  }
 }

}
