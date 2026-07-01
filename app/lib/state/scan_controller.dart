import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/client.dart';
import 'providers.dart';

enum ScanPhase { idle, starting, running, finished, cancelled, error }

class ScanState {
  const ScanState({
    this.phase = ScanPhase.idle,
    this.handle,
    this.baseUrl,
    this.maxDepth = 0,
    this.maxPages = 0,
    this.pagesFound = const [],
    this.pagesSkipped = const [],
    this.result,
    this.errorMessage,
  });

  final ScanPhase phase;
  final JobHandle? handle;
  final String? baseUrl;
  final int maxDepth;
  final int maxPages;
  final List<ScanPageFound> pagesFound;
  final List<ScanPageSkipped> pagesSkipped;
  final ScanResult? result;
  final String? errorMessage;

  bool get isBusy => phase == ScanPhase.starting || phase == ScanPhase.running;
  bool get isTerminal =>
      phase == ScanPhase.finished ||
      phase == ScanPhase.cancelled ||
      phase == ScanPhase.error;

  ScanState copyWith({
    ScanPhase? phase,
    JobHandle? handle,
    String? baseUrl,
    int? maxDepth,
    int? maxPages,
    List<ScanPageFound>? pagesFound,
    List<ScanPageSkipped>? pagesSkipped,
    ScanResult? result,
    String? errorMessage,
  }) {
    return ScanState(
      phase: phase ?? this.phase,
      handle: handle ?? this.handle,
      baseUrl: baseUrl ?? this.baseUrl,
      maxDepth: maxDepth ?? this.maxDepth,
      maxPages: maxPages ?? this.maxPages,
      pagesFound: pagesFound ?? this.pagesFound,
      pagesSkipped: pagesSkipped ?? this.pagesSkipped,
      result: result ?? this.result,
      errorMessage: errorMessage ?? this.errorMessage,
    );
  }
}

class ScanController extends StateNotifier<ScanState> {
  ScanController(this._api, this._projectPath) : super(const ScanState());

  final FuzzmarkApi _api;
  final String _projectPath;
  StreamSubscription<ScanEvent>? _sub;

  Future<void> start(CrawlBoundsRequest bounds) async {
    if (state.isBusy) return;
    await _sub?.cancel();
    _sub = null;
    state = const ScanState(phase: ScanPhase.starting);
    try {
      final handle = await _api.startScan(
        projectPath: _projectPath,
        bounds: bounds,
      );
      state = state.copyWith(phase: ScanPhase.running, handle: handle);
      _sub = _api.streamScanEvents(handle).listen(
        _onEvent,
        onError: _onStreamError,
        onDone: _onStreamDone,
      );
    } catch (exc) {
      state = state.copyWith(
        phase: ScanPhase.error,
        errorMessage: exc.toString(),
      );
    }
  }

  Future<void> cancel() async {
    final handle = state.handle;
    if (handle == null || state.isTerminal) return;
    try {
      await _api.cancelJob(handle.jobId);
    } catch (_) {
      // Terminal event will still be delivered by the stream.
    }
  }

  void reset() {
    _sub?.cancel();
    _sub = null;
    state = const ScanState();
  }

  void _onEvent(ScanEvent event) {
    switch (event) {
      case ScanJobStarted():
        break;
      case ScanStarted(:final baseUrl, :final maxDepth, :final maxPages):
        state = state.copyWith(
          baseUrl: baseUrl,
          maxDepth: maxDepth,
          maxPages: maxPages,
        );
      case ScanPageFound f:
        state = state.copyWith(pagesFound: [...state.pagesFound, f]);
      case ScanPageSkipped s:
        state = state.copyWith(pagesSkipped: [...state.pagesSkipped, s]);
      case ScanFinished(:final result):
        state = state.copyWith(phase: ScanPhase.finished, result: result);
      case ScanCancelled():
        state = state.copyWith(phase: ScanPhase.cancelled);
      case ScanErrored(:final message):
        state = state.copyWith(
          phase: ScanPhase.error,
          errorMessage: message,
        );
      case ScanUnknownEvent():
        break;
    }
  }

  void _onStreamError(Object exc, StackTrace _) {
    if (state.isTerminal) return;
    state = state.copyWith(
      phase: ScanPhase.error,
      errorMessage: exc.toString(),
    );
  }

  void _onStreamDone() {
    _sub = null;
    if (state.isTerminal) return;
    state = state.copyWith(
      phase: ScanPhase.error,
      errorMessage: 'scan job stream closed before a terminal event',
    );
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}

final scanControllerProvider = StateNotifierProvider.autoDispose
    .family<ScanController, ScanState, String>(
  (ref, projectPath) => ScanController(ref.read(apiProvider), projectPath),
);
