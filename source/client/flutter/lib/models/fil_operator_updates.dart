/// Informational metadata only. Never authorizes sessions or installs binaries.
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';

class FilVersion implements Comparable<FilVersion> {
  final List<int> parts;
  final String text;
  FilVersion._(this.parts, this.text);
  factory FilVersion.parse(dynamic value) {
    if (value is! String ||
        !RegExp(r'^(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})(\+(0|[1-9]\d{0,5}))?$')
            .hasMatch(value)) {
      throw const FormatException('invalid_stable_version');
    }
    final p = value.split(RegExp(r'[.+]')).map(int.parse).toList();
    return FilVersion._([...p, if (p.length == 3) 0], value);
  }
  @override
  int compareTo(FilVersion other) {
    for (var i = 0; i < 4; i++) {
      final c = parts[i].compareTo(other.parts[i]);
      if (c != 0) return c;
    }
    return 0;
  }
}

Uri filUpdateInfoUrl(dynamic value) {
  if (value is! String ||
      !RegExp(r'^https://filteknoloji\.com/uzak-destek/operator-surumleri/[a-zA-Z0-9._+-]+$')
          .hasMatch(value)) {
    throw const FormatException('unapproved_information_url');
  }
  final u = Uri.parse(value);
  if (u.scheme != 'https' ||
      u.host != 'filteknoloji.com' ||
      u.userInfo.isNotEmpty ||
      u.hasPort ||
      u.hasQuery ||
      u.hasFragment ||
      !RegExp(r'^/uzak-destek/operator-surumleri/[a-zA-Z0-9._+-]+$')
          .hasMatch(u.path)) {
    throw const FormatException('unapproved_information_url');
  }
  return u;
}

class FilUpdateManifest {
  final FilVersion latest, minimum;
  final DateTime generated, expires, published;
  final Uri infoUrl;
  final String notes;
  final String? baseCommit, baseTag, upstreamVersion;
  final DateTime? upstreamPublished;
  final List<Map<String, String>> advisories;
  FilUpdateManifest._(
      this.latest,
      this.minimum,
      this.generated,
      this.expires,
      this.published,
      this.infoUrl,
      this.notes,
      this.baseCommit,
      this.baseTag,
      this.upstreamVersion,
      this.upstreamPublished,
      this.advisories);
  factory FilUpdateManifest.parse(String body, DateTime now) {
    if (utf8.encode(body).length > 65536) {
      throw const FormatException('oversize');
    }
    final j = jsonDecode(body);
    if (j is! Map ||
        j['schema'] != 1 ||
        j['product'] != 'FilDesk' ||
        j['role'] != 'operator' ||
        j['approved'] != true ||
        j['download_url'] != null) {
      throw const FormatException('role_or_approval_or_binary_url');
    }
    DateTime date(dynamic v) {
      if (v is! String || !v.endsWith('Z')) {
        throw const FormatException('utc_required');
      }
      return DateTime.parse(v).toUtc();
    }

    final generated = date(j['generated_at']), expires = date(j['expires_at']);
    final published = date(j['published_at']);
    if (generated.isAfter(now.add(const Duration(minutes: 5))) ||
        !expires.isAfter(now) ||
        !expires.isAfter(generated) ||
        expires.difference(generated) > const Duration(hours: 48) ||
        published.isAfter(generated)) {
      throw const FormatException('stale_or_invalid_time');
    }
    final latest = FilVersion.parse(j['latest']),
        minimum = FilVersion.parse(j['minimum']);
    if (minimum.compareTo(latest) > 0) {
      throw const FormatException('invalid_minimum');
    }
    final notes = j['notes'];
    if (notes is! String || notes.length > 2000) {
      throw const FormatException('notes');
    }
    final base = j['upstream_base'];
    String? baseCommit, baseTag;
    if (base != null) {
      if (base is! Map ||
          base['commit'] is! String ||
          !RegExp(r'^[a-f0-9]{40}$').hasMatch(base['commit'])) {
        throw const FormatException('base_commit');
      }
      baseCommit = base['commit'];
      if (base['tag'] != null) baseTag = FilVersion.parse(base['tag']).text;
    }
    String? upstreamVersion;
    DateTime? upstreamPublished;
    final upstream = j['upstream'];
    if (upstream != null && upstream is! Map) {
      throw const FormatException('upstream');
    }
    if (upstream is Map &&
        upstream['prerelease'] == false &&
        upstream['draft'] == false) {
      upstreamVersion = FilVersion.parse(upstream['version']).text;
      upstreamPublished = date(upstream['published_at']);
      if (upstreamPublished.isAfter(generated) ||
          upstream['url'] !=
              'https://github.com/rustdesk/rustdesk/releases/tag/$upstreamVersion') {
        throw const FormatException('upstream_origin_or_date');
      }
    }
    final a = j['advisories'];
    if (a is! List || a.length > 20) throw const FormatException('advisories');
    final advisories = <Map<String, String>>[];
    for (final item in a) {
      if (item is! Map ||
          item['id'] is! String ||
          !RegExp(r'^GHSA-[a-z0-9-]{14}$').hasMatch(item['id']) ||
          item['url'] !=
              'https://github.com/rustdesk/rustdesk/security/advisories/${item['id']}' ||
          !['review_required', 'reviewed_not_affected', 'fix_pending']
              .contains(item['status']) ||
          !['unknown', 'low', 'moderate', 'high', 'critical']
              .contains(item['priority'])) {
        throw const FormatException('advisory_origin_or_status');
      }
      advisories.add({
        'id': item['id'],
        'url': item['url'],
        'status': item['status'],
        'priority': item['priority']
      });
    }
    return FilUpdateManifest._(
        latest,
        minimum,
        generated,
        expires,
        published,
        filUpdateInfoUrl(j['information_url']),
        notes,
        baseCommit,
        baseTag,
        upstreamVersion,
        upstreamPublished,
        advisories);
  }
  bool upstreamNewerThanRecordedBase() =>
      upstreamVersion != null &&
      baseTag != null &&
      FilVersion.parse(upstreamVersion).compareTo(FilVersion.parse(baseTag)) >
          0;
}

/// Fixed first-party endpoint; no redirects, credentials, downloads or telemetry.
Future<String> fetchFilOperatorUpdates() async {
  final client = HttpClient()..connectionTimeout = const Duration(seconds: 5);
  try {
    return await (() async {
      final req = await client.getUrl(Uri.parse(
          'https://filteknoloji.com/api/fildesk/updates?role=operator'));
      req.followRedirects = false;
      final res = await req.close();
      if (res.statusCode != 200 ||
          res.headers.contentType?.mimeType != 'application/json') {
        throw const HttpException('update_http_or_mime');
      }
      final bytes = <int>[];
      await for (final chunk in res) {
        if (bytes.length + chunk.length > 65536) {
          throw const FormatException('oversize');
        }
        bytes.addAll(chunk);
      }
      return utf8.decode(bytes);
    })()
        .timeout(const Duration(seconds: 8));
  } finally {
    client.close(force: true);
  }
}

typedef UpdateRead = Future<String> Function();

class FilOperatorUpdateController extends ChangeNotifier {
  final FilVersion installed;
  final UpdateRead fetch;
  final DateTime Function() clock;
  final String Function() readCache;
  final Future<void> Function(String) writeCache;
  final bool Function() sessionActive;
  FilUpdateManifest? manifest;
  DateTime? lastSuccess, nextCheck;
  bool busy = false, failed = false, _disposed = false;
  int _failures = 0;
  FilOperatorUpdateController(
      {required String installed,
      required this.fetch,
      required this.readCache,
      required this.writeCache,
      required this.sessionActive,
      DateTime Function()? clock})
      : installed = FilVersion.parse(installed),
        clock = clock ?? DateTime.now;
  static const recordedUpstreamCommit =
      'fada664df7a294d1d1a9ca3e7cd3637069122f17';
  bool get fresh =>
      manifest != null &&
      lastSuccess != null &&
      !lastSuccess!.isAfter(clock()) &&
      clock().difference(lastSuccess!) < const Duration(hours: 24) &&
      manifest!.expires.isAfter(clock());
  String get label {
    if (failed || !fresh) return 'Güncelleme bilgisi henüz alınamadı';
    if (manifest!.latest.compareTo(installed) > 0) {
      return 'FilDesk güncellemesi mevcut';
    }
    if (manifest!.upstreamNewerThanRecordedBase()) {
      return 'RustDesk kaynak projesinde yeni sürüm';
    }
    if (manifest!.baseCommit == null || manifest!.baseTag == null) {
      return 'Kaynak sürümü karşılaştırması gerekli';
    }
    return 'FilDesk ${installed.text} · Güncel';
  }

  void restore() {
    try {
      final j = jsonDecode(readCache());
      final checked = DateTime.parse(j['checked_at']).toUtc();
      if (checked.isAfter(clock())) return;
      final parsed = FilUpdateManifest.parse(j['body'], clock());
      if (parsed.baseCommit != null &&
          (parsed.baseCommit != recordedUpstreamCommit ||
              parsed.baseTag != '1.5.0')) return;
      manifest = parsed;
      lastSuccess = checked;
      if (fresh) nextCheck = checked.add(const Duration(hours: 24));
    } catch (_) {/* Untrusted, malformed or expired cache is not current. */}
  }

  Future<void> check({bool manual = false}) async {
    final now = clock();
    if (_disposed ||
        busy ||
        sessionActive() ||
        (!manual && nextCheck != null && now.isBefore(nextCheck!)) ||
        (manual &&
            nextCheck != null &&
            _failures > 0 &&
            now.isBefore(nextCheck!))) return;
    busy = true;
    notifyListeners();
    try {
      final raw = await fetch().timeout(const Duration(seconds: 9));
      final value = FilUpdateManifest.parse(raw, clock());
      if (value.baseCommit != null &&
          (value.baseCommit != recordedUpstreamCommit ||
              value.baseTag != '1.5.0')) {
        throw const FormatException('installed_base_mismatch');
      }
      if (_disposed) return;
      manifest = value;
      lastSuccess = clock();
      failed = false;
      _failures = 0;
      nextCheck = lastSuccess!.add(const Duration(hours: 24));
      try {
        await writeCache(jsonEncode({
          'checked_at': lastSuccess!.toUtc().toIso8601String(),
          'body': raw
        })).timeout(const Duration(seconds: 2));
      } catch (_) {/* Cache failure cannot affect support. */}
    } catch (_) {
      if (_disposed) return;
      failed = true;
      _failures = (_failures + 1).clamp(1, 8).toInt();
      nextCheck = clock().add(Duration(minutes: 5 * (1 << (_failures - 1))));
    } finally {
      if (!_disposed) {
        busy = false;
        notifyListeners();
      }
    }
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
