import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api/client.dart';
import 'screens/project_screen.dart';
import 'screens/projects_screen.dart';
import 'state/providers.dart';
import 'state/recents.dart';
import 'theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final recents = await RecentProjects.load();
  runApp(
    ProviderScope(
      overrides: [recentsProvider.overrideWithValue(recents)],
      child: const FuzzmarkApp(),
    ),
  );
}

class FuzzmarkApp extends ConsumerStatefulWidget {
  const FuzzmarkApp({super.key});

  @override
  ConsumerState<FuzzmarkApp> createState() => _FuzzmarkAppState();
}

class _FuzzmarkAppState extends ConsumerState<FuzzmarkApp> {
  FuzzmarkProject? _open;

  void _openProject(FuzzmarkProject project) {
    setState(() => _open = project);
  }

  Future<void> _switchProject(FuzzmarkProject project) async {
    await ref.read(recentsProvider).add(project.path);
    if (!mounted) return;
    setState(() => _open = project);
  }

  void _closeProject() {
    setState(() => _open = null);
  }

  @override
  Widget build(BuildContext context) {
    final boot = ref.watch(engineBootProvider);
    return MaterialApp(
      title: 'Fuzzmark',
      theme: buildLightTheme(),
      darkTheme: buildDarkTheme(),
      themeMode: ThemeMode.system,
      home: boot.when(
        loading: () =>
            const _BootScreen(message: 'Starting fuzzmark engine…'),
        error: (err, _) => _BootScreen(
          message: 'Engine failed to start',
          error: err.toString(),
          onRetry: () => ref.invalidate(engineBootProvider),
        ),
        data: (_) => _open == null
            ? ProjectsScreen(onOpen: _openProject)
            : ProjectScreen(
                project: _open!,
                onClose: _closeProject,
                onSwitchProject: _switchProject,
              ),
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
