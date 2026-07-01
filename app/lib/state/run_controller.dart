import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/client.dart';
import 'providers.dart';

/// Identifies a single run job — the (project, test) pair the RunScreen
/// is looking at. Records give us structural equality for free so
/// `.family` deduplicates identical keys.
typedef RunJobKey = ({String projectPath, String testRelativePath});

enum RunPhase { idle, starting, running, finished, cancelled, error }

class RunState {
  const RunState({
    this.phase = RunPhase.idle,
    this.handle,
    this.testName,
    this.totalSteps = 0,
    this.viewports = const [],
    this.stepsDone = 0,
    this.captures = const [],
    this.consoleErrors = const [],
    this.pageErrors = const [],
    this.failedRequests = const [],
    this.result,
    this.errorMessage,
  });

  final RunPhase phase;
  final JobHandle? handle;
  final String? testName;
  final int totalSteps;
  final List<String> viewports;
  final int stepsDone;
  final List<RunCapture> captures;
  final List<RunConsoleMessage> consoleErrors;
  final List<String> pageErrors;
  final List<RunFailedRequest> failedRequests;
  final RunResult? result;
  final String? errorMessage;

  bool get isBusy => phase == RunPhase.starting || phase == RunPhase.running;
  bool get isTerminal =>
      phase == RunPhase.finished ||
      phase == RunPhase.cancelled ||
      phase == RunPhase.error;

  RunState copyWith({
    RunPhase? phase,
    JobHandle? handle,
    String? testName,
    int? totalSteps,
    List<String>? viewports,
    int? stepsDone,
    List<RunCapture>? captures,
    List<RunConsoleMessage>? consoleErrors,
    List<String>? pageErrors,
    List<RunFailedRequest>? failedRequests,
    RunResult? result,
    String? errorMessage,
  }) {
    return RunState(
      phase: phase ?? this.phase,
      handle: handle ?? this.handle,
      testName: testName ?? this.testName,
      totalSteps: totalSteps ?? this.totalSteps,
      viewports: viewports ?? this.viewports,
      stepsDone: stepsDone ?? this.stepsDone,
      captures: captures ?? this.captures,
      consoleErrors: consoleErrors ?? this.consoleErrors,
      pageErrors: pageErrors ?? this.pageErrors,
      failedRequests: failedRequests ?? this.failedRequests,
      result: result ?? this.result,
      errorMessage: errorMessage ?? this.errorMessage,
    );
  }
}

class RunController extends StateNotifier<RunState> {
  RunController(this._api, this._key) : super(const RunState());

  final FuzzmarkApi _api;
  final RunJobKey _key;
  StreamSubscription<RunEvent>? _sub;

  static const _flushWindow = Duration(milliseconds: 50);
  Timer? _flushTimer;
  final List<RunCapture> _bufCaptures = [];
  final List<RunConsoleMessage> _bufConsole = [];
  final List<String> _bufPage = [];
  final List<RunFailedRequest> _bufFailed = [];
  int _bufStepsDone = 0;
  String? _bufTestName;
  int? _bufTotalSteps;
  List<String>? _bufViewports;
  RunPhase? _bufTerminalPhase;
  RunResult? _bufResult;
  String? _bufErrorMessage;

  Future<void> start({bool headed = false, int? slowMoMs}) async {
    if (state.isBusy) return;
    await _sub?.cancel();
    _sub = null;
    state = const RunState(phase: RunPhase.starting);
    try {
      final handle = await _api.startRun(
        projectPath: _key.projectPath,
        testRelativePath: _key.testRelativePath,
        headed: headed,
        slowMoMs: slowMoMs,
      );
      state = state.copyWith(phase: RunPhase.running, handle: handle);
      _sub = _api.streamRunEvents(handle).listen(
        _onEvent,
        onError: _onStreamError,
        onDone: _onStreamDone,
      );
    } catch (exc) {
      state = state.copyWith(
        phase: RunPhase.error,
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
      // The stream still emits a terminal event when the worker stops,
      // so a failed cancel POST doesn't need special handling here.
    }
  }

  /// Reset back to idle, dropping any in-flight subscription. Screens call
  /// this when they want a fresh state before starting again.
  void reset() {
    _sub?.cancel();
    _sub = null;
    _flushTimer?.cancel();
    _flushTimer = null;
    _clearBuffers();
    state = const RunState();
  }

  void _onEvent(RunEvent event) {
    final terminal = _bufferEvent(event);
    if (terminal) {
      _flushTimer?.cancel();
      _flushTimer = null;
      _flush();
    } else {
      _flushTimer ??= Timer(_flushWindow, _flush);
    }
  }

  bool _bufferEvent(RunEvent event) {
    switch (event) {
      case RunJobStarted():
        return false;
      case RunStarted(
          :final testName,
          :final totalSteps,
          :final viewports,
        ):
        _bufTestName = testName;
        _bufTotalSteps = totalSteps;
        _bufViewports = viewports;
        return false;
      case RunStepStarted():
        return false;
      case RunStepFinished():
        _bufStepsDone += 1;
        return false;
      case RunCaptureEvent(:final capture):
        _bufCaptures.add(capture);
        return false;
      case RunConsoleErrorEvent(:final message):
        _bufConsole.add(message);
        return false;
      case RunPageErrorEvent(:final message):
        _bufPage.add(message);
        return false;
      case RunFailedRequestEvent(:final request):
        _bufFailed.add(request);
        return false;
      case RunFinished(:final result):
        _bufTerminalPhase = RunPhase.finished;
        _bufResult = result;
        return true;
      case RunCancelled():
        _bufTerminalPhase = RunPhase.cancelled;
        return true;
      case RunErrored(:final message):
        _bufTerminalPhase = RunPhase.error;
        _bufErrorMessage = message;
        return true;
      case RunUnknownEvent():
        return false;
    }
  }

  void _flush() {
    _flushTimer = null;
    if (_bufCaptures.isEmpty &&
        _bufConsole.isEmpty &&
        _bufPage.isEmpty &&
        _bufFailed.isEmpty &&
        _bufStepsDone == 0 &&
        _bufTestName == null &&
        _bufTerminalPhase == null) {
      return;
    }
    state = state.copyWith(
      phase: _bufTerminalPhase,
      testName: _bufTestName,
      totalSteps: _bufTotalSteps,
      viewports: _bufViewports,
      stepsDone:
          _bufStepsDone == 0 ? null : state.stepsDone + _bufStepsDone,
      captures: _bufCaptures.isEmpty
          ? null
          : [...state.captures, ..._bufCaptures],
      consoleErrors: _bufConsole.isEmpty
          ? null
          : [...state.consoleErrors, ..._bufConsole],
      pageErrors:
          _bufPage.isEmpty ? null : [...state.pageErrors, ..._bufPage],
      failedRequests: _bufFailed.isEmpty
          ? null
          : [...state.failedRequests, ..._bufFailed],
      result: _bufResult,
      errorMessage: _bufErrorMessage,
    );
    _clearBuffers();
  }

  void _clearBuffers() {
    _bufCaptures.clear();
    _bufConsole.clear();
    _bufPage.clear();
    _bufFailed.clear();
    _bufStepsDone = 0;
    _bufTestName = null;
    _bufTotalSteps = null;
    _bufViewports = null;
    _bufTerminalPhase = null;
    _bufResult = null;
    _bufErrorMessage = null;
  }

  void _onStreamError(Object exc, StackTrace _) {
    if (state.isTerminal) return;
    _flushTimer?.cancel();
    _flushTimer = null;
    _clearBuffers();
    state = state.copyWith(
      phase: RunPhase.error,
      errorMessage: exc.toString(),
    );
  }

  void _onStreamDone() {
    _sub = null;
    if (state.isTerminal) return;
    _flushTimer?.cancel();
    _flushTimer = null;
    _clearBuffers();
    state = state.copyWith(
      phase: RunPhase.error,
      errorMessage: 'run job stream closed before a terminal event',
    );
  }

  @override
  void dispose() {
    _flushTimer?.cancel();
    _sub?.cancel();
    super.dispose();
  }
}

final runControllerProvider = StateNotifierProvider.autoDispose
    .family<RunController, RunState, RunJobKey>(
  (ref, key) => RunController(ref.read(apiProvider), key),
);
