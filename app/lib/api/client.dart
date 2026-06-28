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
  });

  final String url;
  final int depth;
  final String? title;
  final String? error;

  factory ScannedPage.fromJson(Map<String, dynamic> json) => ScannedPage(
        url: json['url'] as String,
        depth: (json['depth'] as num).toInt(),
        title: json['title'] as String?,
        error: json['error'] as String?,
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

  Future<ScanResult> runScan({
    required String projectPath,
    CrawlBoundsRequest bounds = const CrawlBoundsRequest(),
  }) async {
    final res = await _post('/api/projects/scan', {
      'path': projectPath,
      ...bounds.toJson(),
    });
    final siteMap = res['site_map'] as Map<String, dynamic>;
    return ScanResult.fromJson(siteMap);
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
    final res = await _post('/api/projects/extract', {
      'path': projectPath,
      'url': url,
    });
    return (res['fields'] as List? ?? [])
        .map((f) => ExtractedField.fromJson(f as Map<String, dynamic>))
        .toList();
  }

  Future<Map<String, List<FieldSuggestion>>> suggestFields({
    required String projectPath,
    required List<ExtractedField> fields,
  }) async {
    final res = await _post('/api/projects/suggest', {
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

  Future<RunResult> runTest({
    required String projectPath,
    required String testRelativePath,
    bool headed = false,
  }) async {
    final res = await _post('/api/projects/tests/run', {
      'path': projectPath,
      'test': testRelativePath,
      if (headed) 'headed': true,
    });
    return RunResult.fromJson(res);
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
