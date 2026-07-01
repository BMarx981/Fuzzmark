import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

class EngineApiException implements Exception {
  EngineApiException(this.statusCode, this.message);

  final int statusCode;
  final String message;

  @override
  String toString() => 'EngineApiException($statusCode): $message';
}

class FuzzmarkProject {
  FuzzmarkProject({
    required this.path,
    required this.name,
    required this.baseUrl,
    required this.raw,
  });

  final String path;
  final String name;
  final String baseUrl;
  final Map<String, dynamic> raw;

  String? get scan {
    final v = raw['scan'];
    return v is String ? v : null;
  }

  List<String> get tests {
    final v = raw['tests'];
    if (v is! List) return const [];
    return v.whereType<String>().toList(growable: false);
  }

  factory FuzzmarkProject.fromJson(Map<String, dynamic> json) =>
      FuzzmarkProject(
        path: json['path'] as String,
        name: json['name'] as String,
        baseUrl: json['base_url'] as String,
        raw: json,
      );
}

class CrawlBoundsRequest {
  const CrawlBoundsRequest({
    this.maxDepth = 3,
    this.maxPages = 50,
    this.ignoreRobots = false,
    this.allowCrossOrigin = false,
    this.rateLimit = 0.0,
    this.headed = false,
  });

  final int maxDepth;
  final int maxPages;
  final bool ignoreRobots;
  final bool allowCrossOrigin;
  final double rateLimit;
  final bool headed;

  Map<String, dynamic> toJson() => {
        'max_depth': maxDepth,
        'max_pages': maxPages,
        'ignore_robots': ignoreRobots,
        'allow_cross_origin': allowCrossOrigin,
        'rate_limit': rateLimit,
        'headed': headed,
      };
}

class ScannedPage {
  ScannedPage({
    required this.url,
    required this.depth,
    required this.title,
    required this.error,
    required this.ctas,
  });

  final String url;
  final int depth;
  final String? title;
  final String? error;
  final List<ExtractedCta> ctas;

  factory ScannedPage.fromJson(Map<String, dynamic> json) => ScannedPage(
        url: json['url'] as String,
        depth: (json['depth'] as num).toInt(),
        title: json['title'] as String?,
        error: json['error'] as String?,
        ctas: (json['ctas'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(ExtractedCta.fromJson)
            .toList(growable: false),
      );
}

class ScannedSkip {
  ScannedSkip({required this.url, required this.reason});

  final String url;
  final String reason;

  factory ScannedSkip.fromJson(Map<String, dynamic> json) => ScannedSkip(
        url: json['url'] as String,
        reason: json['reason'] as String,
      );
}

class ScanResult {
  ScanResult({
    required this.baseUrl,
    required this.pages,
    required this.skipped,
    required this.raw,
  });

  final String baseUrl;
  final List<ScannedPage> pages;
  final List<ScannedSkip> skipped;
  final Map<String, dynamic> raw;

  factory ScanResult.fromJson(Map<String, dynamic> json) {
    final pages = (json['pages'] as List? ?? [])
        .map((p) => ScannedPage.fromJson(p as Map<String, dynamic>))
        .toList();
    final skipped = (json['skipped'] as List? ?? [])
        .map((s) => ScannedSkip.fromJson(s as Map<String, dynamic>))
        .toList();
    return ScanResult(
      baseUrl: json['base_url'] as String,
      pages: pages,
      skipped: skipped,
      raw: json,
    );
  }
}

class FieldValidation {
  FieldValidation({
    this.required = false,
    this.maxlength,
    this.minlength,
    this.min,
    this.max,
    this.step,
    this.pattern,
    this.accept,
  });

  final bool required;
  final int? maxlength;
  final int? minlength;
  final String? min;
  final String? max;
  final String? step;
  final String? pattern;
  final String? accept;

  factory FieldValidation.fromJson(Map<String, dynamic> json) => FieldValidation(
        required: json['required'] == true,
        maxlength: (json['maxlength'] as num?)?.toInt(),
        minlength: (json['minlength'] as num?)?.toInt(),
        min: json['min'] as String?,
        max: json['max'] as String?,
        step: json['step'] as String?,
        pattern: json['pattern'] as String?,
        accept: json['accept'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'required': required,
        'maxlength': maxlength,
        'minlength': minlength,
        'min': min,
        'max': max,
        'step': step,
        'pattern': pattern,
        'accept': accept,
      };
}

class FieldOption {
  FieldOption({required this.value, required this.label});

  final String value;
  final String label;

  factory FieldOption.fromJson(Map<String, dynamic> json) => FieldOption(
        value: json['value'] as String? ?? '',
        label: json['label'] as String? ?? '',
      );

  Map<String, dynamic> toJson() => {'value': value, 'label': label};
}

class ExtractedField {
  ExtractedField({
    required this.selector,
    required this.kind,
    required this.type,
    required this.name,
    required this.id,
    required this.label,
    required this.validation,
    required this.options,
  });

  final String selector;
  final String kind;
  final String? type;
  final String? name;
  final String? id;
  final String? label;
  final FieldValidation validation;
  final List<FieldOption> options;

  factory ExtractedField.fromJson(Map<String, dynamic> json) => ExtractedField(
        selector: json['selector'] as String,
        kind: json['kind'] as String,
        type: json['type'] as String?,
        name: json['name'] as String?,
        id: json['id'] as String?,
        label: json['label'] as String?,
        validation:
            FieldValidation.fromJson(json['validation'] as Map<String, dynamic>? ?? {}),
        options: (json['options'] as List? ?? [])
            .map((o) => FieldOption.fromJson(o as Map<String, dynamic>))
            .toList(),
      );

  Map<String, dynamic> toJson() => {
        'selector': selector,
        'kind': kind,
        'type': type,
        'name': name,
        'id': id,
        'label': label,
        'validation': validation.toJson(),
        'options': options.map((o) => o.toJson()).toList(),
      };
}

class ExtractedCta {
  ExtractedCta({
    required this.selector,
    required this.kind,
    required this.label,
    required this.href,
    required this.disabled,
  });

  final String selector;
  final String kind;
  final String? label;
  final String? href;
  final bool disabled;

  factory ExtractedCta.fromJson(Map<String, dynamic> json) => ExtractedCta(
        selector: json['selector'] as String,
        kind: json['kind'] as String,
        label: json['label'] as String?,
        href: json['href'] as String?,
        disabled: json['disabled'] == true,
      );
}

class FieldSuggestion {
  FieldSuggestion({
    required this.category,
    required this.value,
    required this.label,
  });

  final String category;
  final String value;
  final String label;

  factory FieldSuggestion.fromJson(Map<String, dynamic> json) => FieldSuggestion(
        category: json['category'] as String,
        value: json['value'] as String? ?? '',
        label: json['label'] as String? ?? '',
      );
}

class RunCapture {
  RunCapture({
    required this.name,
    required this.stepIndex,
    required this.screenshotPath,
    required this.viewport,
  });

  final String name;
  final int stepIndex;
  final String screenshotPath;
  final String? viewport;

  factory RunCapture.fromJson(Map<String, dynamic> json) => RunCapture(
        name: json['name'] as String,
        stepIndex: (json['step_index'] as num).toInt(),
        screenshotPath: json['screenshot_path'] as String,
        viewport: json['viewport'] as String?,
      );
}

class RunConsoleMessage {
  RunConsoleMessage({required this.level, required this.text});

  final String level;
  final String text;

  factory RunConsoleMessage.fromJson(Map<String, dynamic> json) =>
      RunConsoleMessage(
        level: json['level'] as String,
        text: json['text'] as String,
      );
}

class RunFailedRequest {
  RunFailedRequest({
    required this.url,
    required this.method,
    required this.failure,
    required this.status,
  });

  final String url;
  final String method;
  final String? failure;
  final int? status;

  factory RunFailedRequest.fromJson(Map<String, dynamic> json) =>
      RunFailedRequest(
        url: json['url'] as String,
        method: json['method'] as String,
        failure: json['failure'] as String?,
        status: (json['status'] as num?)?.toInt(),
      );
}

class RunResult {
  RunResult({
    required this.testName,
    required this.captures,
    required this.consoleErrors,
    required this.pageErrors,
    required this.failedRequests,
    required this.runDir,
    required this.resultPath,
    required this.raw,
  });

  final String testName;
  final List<RunCapture> captures;
  final List<RunConsoleMessage> consoleErrors;
  final List<String> pageErrors;
  final List<RunFailedRequest> failedRequests;
  final String runDir;
  final String resultPath;
  final Map<String, dynamic> raw;

  bool get hasErrors =>
      consoleErrors.isNotEmpty ||
      pageErrors.isNotEmpty ||
      failedRequests.isNotEmpty;

  factory RunResult.fromJson(Map<String, dynamic> json) {
    final result = json['result'] as Map<String, dynamic>;
    return RunResult(
      testName: result['test_name'] as String,
      captures: (result['captures'] as List? ?? [])
          .map((c) => RunCapture.fromJson(c as Map<String, dynamic>))
          .toList(),
      consoleErrors: (result['console_errors'] as List? ?? [])
          .map((c) => RunConsoleMessage.fromJson(c as Map<String, dynamic>))
          .toList(),
      pageErrors: (result['page_errors'] as List? ?? [])
          .whereType<String>()
          .toList(),
      failedRequests: (result['failed_requests'] as List? ?? [])
          .map((r) => RunFailedRequest.fromJson(r as Map<String, dynamic>))
          .toList(),
      runDir: json['run_dir'] as String,
      resultPath: json['result_path'] as String,
      raw: result,
    );
  }
}

class ReportEntry {
  ReportEntry({
    required this.name,
    required this.stepIndex,
    required this.capturePath,
    required this.verdict,
    required this.baselinePath,
    required this.diffPath,
    required this.score,
    required this.threshold,
    required this.viewport,
  });

  final String name;
  final int stepIndex;
  final String capturePath;
  final String verdict;
  final String? baselinePath;
  final String? diffPath;
  final double? score;
  final double? threshold;
  final String? viewport;

  factory ReportEntry.fromJson(Map<String, dynamic> json) => ReportEntry(
        name: json['name'] as String,
        stepIndex: (json['step_index'] as num).toInt(),
        capturePath: json['capture_path'] as String,
        verdict: json['verdict'] as String,
        baselinePath: json['baseline_path'] as String?,
        diffPath: json['diff_path'] as String?,
        score: (json['score'] as num?)?.toDouble(),
        threshold: (json['threshold'] as num?)?.toDouble(),
        viewport: json['viewport'] as String?,
      );
}

class RunReport {
  RunReport({
    required this.testName,
    required this.entries,
    required this.verdictCounts,
    required this.consoleErrors,
    required this.pageErrors,
    required this.failedRequests,
    required this.reportDir,
    required this.indexPath,
    required this.baselinesDir,
  });

  final String testName;
  final List<ReportEntry> entries;
  final Map<String, int> verdictCounts;
  final List<RunConsoleMessage> consoleErrors;
  final List<String> pageErrors;
  final List<RunFailedRequest> failedRequests;
  final String reportDir;
  final String indexPath;
  final String? baselinesDir;

  bool get hasErrors =>
      consoleErrors.isNotEmpty ||
      pageErrors.isNotEmpty ||
      failedRequests.isNotEmpty;

  factory RunReport.fromJson(Map<String, dynamic> json) {
    final report = json['report'] as Map<String, dynamic>;
    return RunReport(
      testName: report['test_name'] as String? ?? '',
      entries: (report['entries'] as List? ?? [])
          .map((e) => ReportEntry.fromJson(e as Map<String, dynamic>))
          .toList(),
      verdictCounts: (report['verdict_counts'] as Map? ?? {})
          .map((k, v) => MapEntry(k as String, (v as num).toInt())),
      consoleErrors: (report['console_errors'] as List? ?? [])
          .map((c) => RunConsoleMessage.fromJson(c as Map<String, dynamic>))
          .toList(),
      pageErrors: (report['page_errors'] as List? ?? [])
          .whereType<String>()
          .toList(),
      failedRequests: (report['failed_requests'] as List? ?? [])
          .map((r) => RunFailedRequest.fromJson(r as Map<String, dynamic>))
          .toList(),
      reportDir: json['report_dir'] as String,
      indexPath: json['index_path'] as String? ?? '',
      baselinesDir: json['baselines_dir'] as String?,
    );
  }
}

class ApprovalItem {
  ApprovalItem({
    required this.captureName,
    required this.sourcePath,
    required this.targetPath,
    required this.action,
  });

  final String captureName;
  final String sourcePath;
  final String targetPath;
  final String action;

  factory ApprovalItem.fromJson(Map<String, dynamic> json) => ApprovalItem(
        captureName: json['capture_name'] as String,
        sourcePath: json['source_path'] as String,
        targetPath: json['target_path'] as String,
        action: json['action'] as String,
      );
}

class ApprovalSkipped {
  ApprovalSkipped({required this.captureName, required this.reason});

  final String captureName;
  final String reason;

  factory ApprovalSkipped.fromJson(Map<String, dynamic> json) =>
      ApprovalSkipped(
        captureName: json['capture_name'] as String,
        reason: json['reason'] as String,
      );
}

class ApprovalResult {
  ApprovalResult({
    required this.testName,
    required this.baselinesDir,
    required this.dryRun,
    required this.written,
    required this.skipped,
  });

  final String testName;
  final String baselinesDir;
  final bool dryRun;
  final List<ApprovalItem> written;
  final List<ApprovalSkipped> skipped;

  factory ApprovalResult.fromJson(Map<String, dynamic> json) => ApprovalResult(
        testName: json['test_name'] as String? ?? '',
        baselinesDir: json['baselines_dir'] as String? ?? '',
        dryRun: json['dry_run'] == true,
        written: (json['written'] as List? ?? [])
            .map((a) => ApprovalItem.fromJson(a as Map<String, dynamic>))
            .toList(),
        skipped: (json['skipped'] as List? ?? [])
            .map((s) => ApprovalSkipped.fromJson(s as Map<String, dynamic>))
            .toList(),
      );
}

class JobHandle {
  const JobHandle({required this.jobId, required this.kind});

  final String jobId;
  final String kind;

  factory JobHandle.fromJson(Map<String, dynamic> json) => JobHandle(
        jobId: json['job_id'] as String,
        kind: json['kind'] as String,
      );

  @override
  String toString() => 'JobHandle($kind:$jobId)';
}

class JobSnapshot {
  const JobSnapshot({
    required this.jobId,
    required this.kind,
    required this.state,
    required this.startedAt,
    required this.result,
    required this.error,
  });

  final String jobId;
  final String kind;
  final String state;
  final double startedAt;
  final Map<String, dynamic>? result;
  final String? error;

  bool get isTerminal =>
      state == 'finished' || state == 'cancelled' || state == 'error';

  factory JobSnapshot.fromJson(Map<String, dynamic> json) => JobSnapshot(
        jobId: json['job_id'] as String,
        kind: json['kind'] as String,
        state: json['state'] as String,
        startedAt: (json['started_at'] as num?)?.toDouble() ?? 0.0,
        result: json['result'] as Map<String, dynamic>?,
        error: json['error'] as String?,
      );
}

sealed class RunEvent {
  const RunEvent();
}

class RunJobStarted extends RunEvent {
  const RunJobStarted();
}

class RunStarted extends RunEvent {
  const RunStarted({
    required this.testName,
    required this.totalSteps,
    required this.viewports,
  });

  final String testName;
  final int totalSteps;
  final List<String> viewports;
}

class RunStepStarted extends RunEvent {
  const RunStepStarted({
    required this.index,
    required this.kind,
    required this.viewport,
  });

  final int index;
  final String kind;
  final String? viewport;
}

class RunStepFinished extends RunEvent {
  const RunStepFinished({
    required this.index,
    required this.kind,
    required this.viewport,
  });

  final int index;
  final String kind;
  final String? viewport;
}

class RunCaptureEvent extends RunEvent {
  const RunCaptureEvent(this.capture);

  final RunCapture capture;
}

class RunConsoleErrorEvent extends RunEvent {
  const RunConsoleErrorEvent({required this.message, required this.viewport});

  final RunConsoleMessage message;
  final String? viewport;
}

class RunPageErrorEvent extends RunEvent {
  const RunPageErrorEvent({required this.message, required this.viewport});

  final String message;
  final String? viewport;
}

class RunFailedRequestEvent extends RunEvent {
  const RunFailedRequestEvent({required this.request, required this.viewport});

  final RunFailedRequest request;
  final String? viewport;
}

class RunFinished extends RunEvent {
  const RunFinished(this.result);

  final RunResult result;
}

class RunCancelled extends RunEvent {
  const RunCancelled();
}

class RunErrored extends RunEvent {
  const RunErrored(this.message);

  final String message;
}

class RunUnknownEvent extends RunEvent {
  const RunUnknownEvent(this.kind, this.raw);

  final String kind;
  final Map<String, dynamic> raw;
}

sealed class ScanEvent {
  const ScanEvent();
}

class ScanJobStarted extends ScanEvent {
  const ScanJobStarted();
}

class ScanStarted extends ScanEvent {
  const ScanStarted({
    required this.baseUrl,
    required this.maxDepth,
    required this.maxPages,
  });

  final String baseUrl;
  final int maxDepth;
  final int maxPages;
}

class ScanPageFound extends ScanEvent {
  const ScanPageFound({
    required this.url,
    required this.depth,
    required this.title,
    required this.error,
    required this.ctaCount,
  });

  final String url;
  final int depth;
  final String? title;
  final String? error;
  final int ctaCount;
}

class ScanPageSkipped extends ScanEvent {
  const ScanPageSkipped({required this.url, required this.reason});

  final String url;
  final String reason;
}

class ScanFinished extends ScanEvent {
  const ScanFinished(this.result);

  final ScanResult result;
}

class ScanCancelled extends ScanEvent {
  const ScanCancelled();
}

class ScanErrored extends ScanEvent {
  const ScanErrored(this.message);

  final String message;
}

class ScanUnknownEvent extends ScanEvent {
  const ScanUnknownEvent(this.kind, this.raw);

  final String kind;
  final Map<String, dynamic> raw;
}

class FuzzmarkApi {
  FuzzmarkApi({Uri? baseUri, http.Client? client})
      : baseUri = baseUri ?? Uri.parse('http://127.0.0.1:8765'),
        _client = client ?? http.Client();

  final Uri baseUri;
  final http.Client _client;

  void close() => _client.close();

  Future<Map<String, dynamic>> health() async {
    final res = await _get('/api/health');
    return res;
  }

  Future<FuzzmarkProject> loadProject(String path) async {
    final res = await _post('/api/projects/load', {'path': path});
    return FuzzmarkProject.fromJson(res);
  }

  Future<JobHandle> startScan({
    required String projectPath,
    CrawlBoundsRequest bounds = const CrawlBoundsRequest(),
  }) async {
    final res = await _post('/api/jobs/scan', {
      'path': projectPath,
      ...bounds.toJson(),
    });
    return JobHandle.fromJson(res);
  }

  Stream<ScanEvent> streamScanEvents(JobHandle handle) async* {
    await for (final raw in _streamJobEvents(handle.jobId)) {
      yield _parseScanEvent(raw);
    }
  }

  Future<ScanResult> fetchScanResult(JobHandle handle) async {
    final snapshot = await fetchJob(handle.jobId);
    return _scanResultFromSnapshot(snapshot);
  }

  Future<JobHandle> startRun({
    required String projectPath,
    required String testRelativePath,
    bool headed = false,
    int? slowMoMs,
  }) async {
    final res = await _post('/api/jobs/run', {
      'path': projectPath,
      'test': testRelativePath,
      if (headed) 'headed': true,
      'slow_mo_ms': ?slowMoMs,
    });
    return JobHandle.fromJson(res);
  }

  Stream<RunEvent> streamRunEvents(JobHandle handle) async* {
    await for (final raw in _streamJobEvents(handle.jobId)) {
      yield _parseRunEvent(raw);
    }
  }

  Future<RunResult> fetchRunResult(JobHandle handle) async {
    final snapshot = await fetchJob(handle.jobId);
    return _runResultFromSnapshot(snapshot);
  }

  Future<JobSnapshot> fetchJob(String jobId) async {
    final res = await _get('/api/jobs/$jobId');
    return JobSnapshot.fromJson(res);
  }

  Future<void> cancelJob(String jobId) async {
    await _post('/api/jobs/$jobId/cancel', const {});
  }

  /// Start a background job, drain its SSE stream, and return the worker's
  /// terminal `result` dict. Throws on `cancelled` / `error` terminal events.
  /// Used for the cheap one-shot endpoints whose call sites don't need
  /// progress events.
  Future<Map<String, dynamic>> runJobToCompletion(
    String kind,
    Map<String, dynamic> body,
  ) async {
    final handle = await _startJob(kind, body);
    await for (final raw in _streamJobEvents(handle.jobId)) {
      final eventKind = raw['event'] as String?;
      if (eventKind == 'finished') {
        return (raw['result'] as Map<String, dynamic>?) ?? <String, dynamic>{};
      }
      if (eventKind == 'cancelled') {
        throw EngineApiException(0, '$kind job cancelled');
      }
      if (eventKind == 'error') {
        throw EngineApiException(
          500,
          (raw['message'] as String?) ?? '$kind failed',
        );
      }
    }
    throw EngineApiException(
      0,
      '$kind job stream ended without a terminal event',
    );
  }

  Future<FuzzmarkProject> saveScan({
    required String projectPath,
    required Map<String, dynamic> siteMap,
    String? filename,
  }) async {
    final res = await _post('/api/projects/scan/save', {
      'path': projectPath,
      'site_map': siteMap,
      'filename': ?filename,
    });
    return FuzzmarkProject.fromJson(res);
  }

  Future<List<ScannedPage>> listScannedPages(String projectPath) async {
    final res = await _post('/api/projects/pages', {'path': projectPath});
    return (res['pages'] as List? ?? [])
        .map((p) => ScannedPage.fromJson(p as Map<String, dynamic>))
        .toList();
  }

  Future<List<ExtractedField>> extractFields({
    required String projectPath,
    required String url,
  }) async {
    final res = await runJobToCompletion('extract', {
      'path': projectPath,
      'url': url,
    });
    return (res['fields'] as List? ?? [])
        .map((f) => ExtractedField.fromJson(f as Map<String, dynamic>))
        .toList();
  }

  Future<List<ExtractedCta>> extractCtas({
    required String projectPath,
    required String url,
  }) async {
    final res = await runJobToCompletion('ctas', {
      'path': projectPath,
      'url': url,
    });
    return (res['ctas'] as List? ?? [])
        .map((c) => ExtractedCta.fromJson(c as Map<String, dynamic>))
        .toList();
  }

  Future<Map<String, List<FieldSuggestion>>> suggestFields({
    required String projectPath,
    required List<ExtractedField> fields,
  }) async {
    final res = await runJobToCompletion('suggest', {
      'path': projectPath,
      'fields': fields.map((f) => f.toJson()).toList(),
    });
    final raw = res['suggestions'] as Map<String, dynamic>? ?? {};
    return raw.map((selector, items) => MapEntry(
          selector,
          (items as List)
              .map((s) => FieldSuggestion.fromJson(s as Map<String, dynamic>))
              .toList(),
        ));
  }

  Future<FuzzmarkProject> saveTest({
    required String projectPath,
    required Map<String, dynamic> test,
    String? filename,
    bool force = false,
  }) async {
    final res = await _post('/api/projects/tests/save', {
      'path': projectPath,
      'test': test,
      'filename': ?filename,
      if (force) 'force': true,
    });
    return FuzzmarkProject.fromJson(res);
  }

  Future<RunReport> reportTest({
    required String projectPath,
    required Map<String, dynamic> result,
    double? threshold,
  }) async {
    final res = await _post('/api/projects/tests/report', {
      'path': projectPath,
      'result': result,
      'threshold': ?threshold,
    });
    return RunReport.fromJson(res);
  }

  Future<ApprovalResult> approveBaselines({
    required String projectPath,
    required Map<String, dynamic> result,
    List<String>? captureNames,
    bool dryRun = false,
  }) async {
    final res = await _post('/api/projects/baselines/approve', {
      'path': projectPath,
      'result': result,
      'captures': ?captureNames,
      if (dryRun) 'dry_run': true,
    });
    return ApprovalResult.fromJson(res);
  }

  Future<FuzzmarkProject> initProject({
    required String path,
    required String name,
    required String baseUrl,
    List<Map<String, dynamic>> viewports = const [],
    bool force = false,
  }) async {
    final res = await _post('/api/projects/init', {
      'path': path,
      'name': name,
      'base_url': baseUrl,
      if (viewports.isNotEmpty) 'viewports': viewports,
      if (force) 'force': true,
    });
    return FuzzmarkProject.fromJson(res);
  }

  Future<FuzzmarkProject> setBaseUrl({
    required String projectPath,
    required String baseUrl,
  }) async {
    final res = await _post('/api/projects/base_url', {
      'path': projectPath,
      'base_url': baseUrl,
    });
    return FuzzmarkProject.fromJson(res);
  }

  Future<JobHandle> _startJob(String kind, Map<String, dynamic> body) async {
    final res = await _post('/api/jobs/$kind', body);
    return JobHandle.fromJson(res);
  }

  /// Stream the raw JSON event objects from a job's SSE endpoint until the
  /// terminal event is consumed and the engine closes the connection. SSE
  /// keepalive comments (`: …`) are silently dropped.
  Stream<Map<String, dynamic>> _streamJobEvents(String jobId) async* {
    final uri = baseUri.replace(path: '/api/jobs/$jobId/events');
    final request = http.Request('GET', uri)
      ..headers['Accept'] = 'text/event-stream';
    final response = await _client.send(request);
    if (response.statusCode >= 400) {
      final body = await response.stream.bytesToString();
      Map<String, dynamic> decoded = const {};
      if (body.isNotEmpty) {
        try {
          decoded = jsonDecode(body) as Map<String, dynamic>;
        } catch (_) {
          // fall through to body-as-message
        }
      }
      final msg = decoded['error']?.toString() ?? (body.isEmpty ? 'request failed' : body);
      throw EngineApiException(response.statusCode, msg);
    }

    final lines = response.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter());
    final dataBuffer = StringBuffer();
    await for (final line in lines) {
      if (line.isEmpty) {
        if (dataBuffer.isEmpty) continue;
        final payload = dataBuffer.toString();
        dataBuffer.clear();
        final decoded = jsonDecode(payload) as Map<String, dynamic>;
        yield decoded;
      } else if (line.startsWith('data: ')) {
        if (dataBuffer.isNotEmpty) dataBuffer.write('\n');
        dataBuffer.write(line.substring(6));
      } else if (line.startsWith('data:')) {
        if (dataBuffer.isNotEmpty) dataBuffer.write('\n');
        dataBuffer.write(line.substring(5));
      }
      // `:`-prefixed comment lines are SSE keepalives — ignore.
    }
  }

  RunEvent _parseRunEvent(Map<String, dynamic> e) {
    final kind = e['event'] as String? ?? '';
    switch (kind) {
      case 'job_started':
        return const RunJobStarted();
      case 'started':
        return RunStarted(
          testName: e['test_name'] as String? ?? '',
          totalSteps: (e['total_steps'] as num?)?.toInt() ?? 0,
          viewports: (e['viewports'] as List? ?? const [])
              .whereType<String>()
              .toList(growable: false),
        );
      case 'step_started':
        return RunStepStarted(
          index: (e['index'] as num).toInt(),
          kind: e['kind'] as String? ?? '',
          viewport: e['viewport'] as String?,
        );
      case 'step_finished':
        return RunStepFinished(
          index: (e['index'] as num).toInt(),
          kind: e['kind'] as String? ?? '',
          viewport: e['viewport'] as String?,
        );
      case 'capture':
        return RunCaptureEvent(RunCapture(
          name: e['name'] as String,
          stepIndex: (e['index'] as num).toInt(),
          screenshotPath: e['screenshot_path'] as String,
          viewport: e['viewport'] as String?,
        ));
      case 'console_error':
        return RunConsoleErrorEvent(
          message: RunConsoleMessage(
            level: e['level'] as String? ?? 'log',
            text: e['text'] as String? ?? '',
          ),
          viewport: e['viewport'] as String?,
        );
      case 'page_error':
        return RunPageErrorEvent(
          message: e['message'] as String? ?? '',
          viewport: e['viewport'] as String?,
        );
      case 'failed_request':
        return RunFailedRequestEvent(
          request: RunFailedRequest(
            url: e['url'] as String,
            method: e['method'] as String? ?? 'GET',
            failure: e['failure'] as String?,
            status: (e['status'] as num?)?.toInt(),
          ),
          viewport: e['viewport'] as String?,
        );
      case 'finished':
        return RunFinished(
          RunResult.fromJson(e['result'] as Map<String, dynamic>),
        );
      case 'cancelled':
        return const RunCancelled();
      case 'error':
        return RunErrored(e['message'] as String? ?? 'run job failed');
      default:
        return RunUnknownEvent(kind, e);
    }
  }

  ScanEvent _parseScanEvent(Map<String, dynamic> e) {
    final kind = e['event'] as String? ?? '';
    switch (kind) {
      case 'job_started':
        return const ScanJobStarted();
      case 'started':
        return ScanStarted(
          baseUrl: e['base_url'] as String? ?? '',
          maxDepth: (e['max_depth'] as num?)?.toInt() ?? 0,
          maxPages: (e['max_pages'] as num?)?.toInt() ?? 0,
        );
      case 'page_found':
        return ScanPageFound(
          url: e['url'] as String,
          depth: (e['depth'] as num?)?.toInt() ?? 0,
          title: e['title'] as String?,
          error: e['error'] as String?,
          ctaCount: (e['cta_count'] as num?)?.toInt() ?? 0,
        );
      case 'page_skipped':
        return ScanPageSkipped(
          url: e['url'] as String,
          reason: e['reason'] as String? ?? '',
        );
      case 'finished':
        final result = e['result'] as Map<String, dynamic>;
        final siteMap = result['site_map'] as Map<String, dynamic>;
        return ScanFinished(ScanResult.fromJson(siteMap));
      case 'cancelled':
        return const ScanCancelled();
      case 'error':
        return ScanErrored(e['message'] as String? ?? 'scan job failed');
      default:
        return ScanUnknownEvent(kind, e);
    }
  }

  RunResult _runResultFromSnapshot(JobSnapshot snapshot) {
    switch (snapshot.state) {
      case 'finished':
        final result = snapshot.result;
        if (result == null) {
          throw EngineApiException(0, 'run job finished without a result');
        }
        return RunResult.fromJson(result);
      case 'cancelled':
        throw EngineApiException(0, 'run job cancelled');
      case 'error':
        throw EngineApiException(500, snapshot.error ?? 'run job failed');
      default:
        throw EngineApiException(0, 'run job not finished (state=${snapshot.state})');
    }
  }

  ScanResult _scanResultFromSnapshot(JobSnapshot snapshot) {
    switch (snapshot.state) {
      case 'finished':
        final result = snapshot.result;
        if (result == null) {
          throw EngineApiException(0, 'scan job finished without a result');
        }
        final siteMap = result['site_map'] as Map<String, dynamic>;
        return ScanResult.fromJson(siteMap);
      case 'cancelled':
        throw EngineApiException(0, 'scan job cancelled');
      case 'error':
        throw EngineApiException(500, snapshot.error ?? 'scan job failed');
      default:
        throw EngineApiException(0, 'scan job not finished (state=${snapshot.state})');
    }
  }

  Future<Map<String, dynamic>> _get(String path) async {
    final res = await _client.get(baseUri.replace(path: path));
    return _decode(res);
  }

  Future<Map<String, dynamic>> _post(String path, Map<String, dynamic> body) async {
    final res = await _client.post(
      baseUri.replace(path: path),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _decode(res);
  }

  Map<String, dynamic> _decode(http.Response res) {
    final decoded = res.body.isEmpty
        ? <String, dynamic>{}
        : jsonDecode(res.body) as Map<String, dynamic>;
    if (res.statusCode >= 400) {
      final msg = decoded['error']?.toString() ?? 'request failed';
      throw EngineApiException(res.statusCode, msg);
    }
    return decoded;
  }
}
