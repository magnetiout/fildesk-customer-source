import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_hbb/models/fil_elevation_wait.dart';
void main() {
  testWidgets('an older elevation deadline cannot dismiss a later request', (tester) async {
    final wait=FilElevationWait();var expired=0;
    wait.start(const Duration(seconds:5),(){expired+=100;});
    await tester.pump(const Duration(seconds:2));
    wait.start(const Duration(seconds:5),(){expired++;});
    await tester.pump(const Duration(seconds:3));expect(expired,0);
    await tester.pump(const Duration(seconds:2));expect(expired,1);
    wait.cancel();
  });
  testWidgets('cancelled/successful dialog does not revive at its old deadline', (tester) async {
    final wait=FilElevationWait();var expired=0;
    wait.start(const Duration(seconds:5),(){expired++;});wait.cancel();
    await tester.pump(const Duration(seconds:95));expect(expired,0);
  });
}
