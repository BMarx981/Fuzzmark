import 'package:flutter/material.dart';

import 'api/client.dart';
import 'screens/project_screen.dart';
import 'screens/projects_screen.dart';
import 'state/recents.dart';
import 'theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final recents = await RecentProjects.load();
  runApp(FuzzmarkApp(recents: recents));
}

class FuzzmarkApp extends StatefulWidget {
  const FuzzmarkApp({super.key, required this.recents});

  final RecentProjects recents;

  @override
  State<FuzzmarkApp> createState() => _FuzzmarkAppState();
}

class _FuzzmarkAppState extends State<FuzzmarkApp> {
  final _api = FuzzmarkApi();
  FuzzmarkProject? _open;

  @override
  void dispose() {
    _api.close();
    super.dispose();
  }

  void _openProject(FuzzmarkProject project) {
    setState(() => _open = project);
  }

  void _closeProject() {
    setState(() => _open = null);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Fuzzmark',
      theme: buildLightTheme(),
      darkTheme: buildDarkTheme(),
      themeMode: ThemeMode.system,
      home: _open == null
          ? ProjectsScreen(
              api: _api,
              recents: widget.recents,
              onOpen: _openProject,
            )
          : ProjectScreen(
              api: _api,
              project: _open!,
              onClose: _closeProject,
            ),
    );
  }
}
