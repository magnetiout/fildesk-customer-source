import 'dart:async';
import '../lib/models/fil_first_frame_wait.dart';
class ControlledTimer implements Timer {
  final void Function() callback;
  bool isActive = true;
  int tick = 0;
  ControlledTimer(this.callback);
  void cancel() { isActive = false; }
  void fire({bool stale = false}) { if (isActive || stale) { tick++; callback(); } }
}
void expect(bool value, String message) { if (!value) throw StateError(message); }
void main() {
  final timers = <ControlledTimer>[];
  final failures = <FilFirstFramePhase>[];
  final wait = FilFirstFrameWait(schedule: (_, callback) { final t = ControlledTimer(callback);timers.add(t);return t; });
  final old = wait.begin(failures.add);
  wait.peerInfo(old, failures.add);
  final videoTimer = timers.last;
  wait.peerInfo(old, failures.add);
  expect(identical(videoTimer, timers.last), 'duplicate peer info renewed deadline');
  videoTimer.fire();
  expect(failures.single == FilFirstFramePhase.waitingVideo, 'missing decoded frame must fail');
  expect(!wait.frameReady(old), 'late frame cannot revive failed session');
  final current = wait.begin(failures.add);
  timers.first.fire(stale: true);
  expect(failures.length == 1, 'stale timeout affected reconnect');
  wait.peerInfo(current, failures.add);
  expect(!wait.frameReady(old), 'stale decode accepted after reconnect');
  expect(wait.frameReady(current), 'valid decoded current frame rejected');
  timers.last.fire(stale: true);
  expect(failures.length == 1, 'ready frame still timed out');
  wait.begin(failures.add); wait.cancel();timers.last.fire(stale: true);
  expect(failures.length == 1, 'cancelled session still timed out');
  wait.begin(failures.add);timers.last.fire();
  expect(failures.last == FilFirstFramePhase.authentication, 'login spinner is unbounded');
  print('PASS: bounded login/video, duplicate events, stale reconnect, valid frame and cancellation');
}
