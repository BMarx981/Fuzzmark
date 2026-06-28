import 'package:shared_preferences/shared_preferences.dart';

class RecentProjects {
  RecentProjects(this._prefs);

  static const _key = 'recent_projects';
  static const _max = 10;

  final SharedPreferences _prefs;

  static Future<RecentProjects> load() async {
    final prefs = await SharedPreferences.getInstance();
    return RecentProjects(prefs);
  }

  List<String> get paths => _prefs.getStringList(_key) ?? const [];

  Future<void> add(String path) async {
    final next = [path, ...paths.where((p) => p != path)].take(_max).toList();
    await _prefs.setStringList(_key, next);
  }

  Future<void> remove(String path) async {
    final next = paths.where((p) => p != path).toList();
    await _prefs.setStringList(_key, next);
  }
}
