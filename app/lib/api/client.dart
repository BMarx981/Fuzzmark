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
