import 'dart:async';

/// Per-dialog deadline; rescheduling/cancellation invalidates the older callback.
class FilElevationWait {
  Timer? _timer;
  int _generation = 0;
  void start(Duration duration, void Function() expire) {
    cancel();
    final generation = ++_generation;
    _timer = Timer(duration, () {
      if (generation != _generation) return;
      _timer = null;
      expire();
    });
  }
  void cancel() { ++_generation; _timer?.cancel(); _timer = null; }
}
