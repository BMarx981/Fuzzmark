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

  factory FuzzmarkProject.fromJson(Map<String, dynamic> json) =>
      FuzzmarkProject(
        path: json['path'] as String,
        name: json['name'] as String,
        baseUrl: json['base_url'] as String,
        raw: json,
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
