import 'dart:async';
import 'dart:io';

import 'package:http/http.dart' as http;

class EngineStartupException implements Exception {
  EngineStartupException(this.message);
  final String message;
  @override
  String toString() => 'EngineStartupException: $message';
}

class EngineProcess {
  EngineProcess({
    this.host = '127.0.0.1',
    this.port = 8765,
    this.bootTimeout = const Duration(seconds: 15),
  });

  final String host;
  final int port;
  final Duration bootTimeout;

  Process? _proc;
  bool _ownsProcess = false;

  Uri get healthUri => Uri.parse('http://$host:$port/api/health');

  Future<void> start() async {
    if (await _isUp()) {
      _ownsProcess = false;
      return;
    }

    final bin = _findBinary();
    if (bin == null) {
      throw EngineStartupException(
        'Could not locate fuzzmark binary. '
        'Set FUZZMARK_BIN or ensure engine/.venv/bin/fuzzmark exists.',
      );
    }

    _proc = await Process.start(
      bin,
      ['serve', '--host', host, '--port', '$port'],
      mode: ProcessStartMode.normal,
    );
    _ownsProcess = true;
    _proc!.stdout.listen(stdout.add);
    _proc!.stderr.listen(stderr.add);

    final deadline = DateTime.now().add(bootTimeout);
    while (DateTime.now().isBefore(deadline)) {
      if (await _isUp()) return;
      await Future<void>.delayed(const Duration(milliseconds: 200));
    }

    await stop();
    throw EngineStartupException(
      'fuzzmark serve did not become ready within ${bootTimeout.inSeconds}s '
      '(checked $healthUri).',
    );
  }

  Future<void> stop() async {
    final p = _proc;
    if (p != null && _ownsProcess) {
      p.kill(ProcessSignal.sigterm);
      try {
        await p.exitCode.timeout(const Duration(seconds: 3));
      } on TimeoutException {
        p.kill(ProcessSignal.sigkill);
      }
    }
    _proc = null;
    _ownsProcess = false;
  }

  Future<bool> _isUp() async {
    try {
      final res = await http
          .get(healthUri)
          .timeout(const Duration(milliseconds: 500));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  String? _findBinary() {
    final override = Platform.environment['FUZZMARK_BIN'];
    if (override != null && override.isNotEmpty) {
      if (File(override).existsSync()) return override;
    }

    var dir = Directory.current;
    for (var i = 0; i < 6; i++) {
      final candidate = File('${dir.path}/engine/.venv/bin/fuzzmark');
      if (candidate.existsSync()) return candidate.path;
      final parent = dir.parent;
      if (parent.path == dir.path) break;
      dir = parent;
    }
    return null;
  }
}
