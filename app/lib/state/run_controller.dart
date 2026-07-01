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
    state = const RunState();
  }

  void _onEvent(RunEvent event) {
    switch (event) {
      case RunJobStarted():
        break;
      case RunStarted(
          :final testName,
          :final totalSteps,
          :final viewports,
        ):
        state = state.copyWith(
          testName: testName,
          totalSteps: totalSteps,
          viewports: viewports,
        );
      case RunStepStarted():
        break;
      case RunStepFinished():
        state = state.copyWith(stepsDone: state.stepsDone + 1);
      case RunCaptureEvent(:final capture):
        state = state.copyWith(captures: [...state.captures, capture]);
      case RunConsoleErrorEvent(:final message):
        state = state.copyWith(
          consoleErrors: [...state.consoleErrors, message],
        );
      case RunPageErrorEvent(:final message):
        state = state.copyWith(pageErrors: [...state.pageErrors, message]);
      case RunFailedRequestEvent(:final request):
        state = state.copyWith(
          failedRequests: [...state.failedRequests, request],
        );
      case RunFinished(:final result):
        state = state.copyWith(phase: RunPhase.finished, result: result);
      case RunCancelled():
        state = state.copyWith(phase: RunPhase.cancelled);
      case RunErrored(:final message):
        state = state.copyWith(
          phase: RunPhase.error,
          errorMessage: message,
        );
      case RunUnknownEvent():
        break;
    }
  }

  void _onStreamError(Object exc, StackTrace _) {
    if (state.isTerminal) return;
    state = state.copyWith(
      phase: RunPhase.error,
      errorMessage: exc.toString(),
    );
  }

  void _onStreamDone() {
    _sub = null;
    if (state.isTerminal) return;
    state = state.copyWith(
      phase: RunPhase.error,
      errorMessage: 'run job stream closed before a terminal event',
    );
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}

final runControllerProvider = StateNotifierProvider.autoDispose
    .family<RunController, RunState, RunJobKey>(
  (ref, key) => RunController(ref.read(apiProvider), key),
);
