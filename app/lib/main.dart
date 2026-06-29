import 'package:flutter/material.dart';

import 'api/client.dart';
import 'engine/engine_process.dart';
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
  final _engine = EngineProcess();
  final _api = FuzzmarkApi();
  FuzzmarkProject? _open;
  late Future<void> _bootFuture;

  @override
  void initState() {
    super.initState();
    _bootFuture = _engine.start();
  }

  @override
  void dispose() {
    _api.close();
    _engine.stop();
    super.dispose();
  }

  void _openProject(FuzzmarkProject project) {
    setState(() => _open = project);
  }

  Future<void> _switchProject(FuzzmarkProject project) async {
    await widget.recents.add(project.path);
    if (!mounted) return;
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
      home: FutureBuilder<void>(
        future: _bootFuture,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const _BootScreen(message: 'Starting fuzzmark engine…');
          }
          if (snap.hasError) {
            return _BootScreen(
              message: 'Engine failed to start',
              error: snap.error.toString(),
              onRetry: () =>
                  setState(() => _bootFuture = _engine.start()),
            );
          }
          return _open == null
              ? ProjectsScreen(
                  api: _api,
                  recents: widget.recents,
                  onOpen: _openProject,
                )
              : ProjectScreen(
                  api: _api,
                  project: _open!,
                  onClose: _closeProject,
                  onSwitchProject: _switchProject,
                );
        },
      ),
    );
  }
}

class _BootScreen extends StatelessWidget {
  const _BootScreen({
    required this.message,
    this.error,
    this.onRetry,
  });

  final String message;
  final String? error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (error == null)
                const CircularProgressIndicator()
              else
                Icon(Icons.error_outline,
                    size: 48, color: theme.colorScheme.error),
              const SizedBox(height: 16),
              Text(message, style: theme.textTheme.titleMedium),
              if (error != null) ...[
                const SizedBox(height: 12),
                SelectableText(
                  error!,
                  style: theme.textTheme.bodySmall,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: onRetry,
                  child: const Text('Retry'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
