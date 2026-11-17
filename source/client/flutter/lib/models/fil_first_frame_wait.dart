import 'dart:async';

enum FilFirstFramePhase { authentication, waitingVideo, frameReady, failed, cancelled }

/// Packet keepalives do not renew the time allowed to produce a usable frame.
class FilFirstFrameWait {
  final Timer Function(Duration, void Function()) schedule;
  final Duration authenticationLimit;
  final Duration videoLimit;
  Timer? _timer;
  int _generation = 0;
  FilFirstFramePhase phase = FilFirstFramePhase.cancelled;
  int get generation => _generation;

  FilFirstFrameWait({Timer Function(Duration, void Function())? schedule,
      this.authenticationLimit = const Duration(seconds: 210),
      this.videoLimit = const Duration(seconds: 30)})
      : schedule = schedule ?? ((duration, callback) => Timer(duration, callback));

  int begin(void Function(FilFirstFramePhase) onTimeout) {
    _timer?.cancel();
    final generation = ++_generation;
    phase = FilFirstFramePhase.authentication;
    _arm(generation, authenticationLimit, onTimeout);
    return generation;
  }

  void peerInfo(int generation, void Function(FilFirstFramePhase) onTimeout) {
    if (generation != _generation || phase != FilFirstFramePhase.authentication) return;
    phase = FilFirstFramePhase.waitingVideo;
    _timer?.cancel();
    _arm(generation, videoLimit, onTimeout);
  }

  void _arm(int generation, Duration duration, void Function(FilFirstFramePhase) onTimeout) {
    _timer = schedule(duration, () {
      if (generation != _generation ||
          (phase != FilFirstFramePhase.authentication && phase != FilFirstFramePhase.waitingVideo)) return;
      final expired = phase;
      phase = FilFirstFramePhase.failed;
      onTimeout(expired);
    });
  }

  bool frameReady(int generation) {
    if (generation != _generation) return false;
    if (phase == FilFirstFramePhase.frameReady) return true;
    if (phase != FilFirstFramePhase.waitingVideo) return false;
    _timer?.cancel();
    phase = FilFirstFramePhase.frameReady;
    return true;
  }

  void cancel() {
    _timer?.cancel();
    ++_generation;
    phase = FilFirstFramePhase.cancelled;
  }
}
