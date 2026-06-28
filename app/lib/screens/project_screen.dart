import 'package:flutter/material.dart';

import '../api/client.dart';
import 'run_screen.dart';
import 'scan_screen.dart';
import 'test_builder_screen.dart';

class ProjectScreen extends StatefulWidget {
  const ProjectScreen({
    super.key,
    required this.api,
    required this.project,
    required this.onClose,
  });

  final FuzzmarkApi api;
  final FuzzmarkProject project;
  final VoidCallback onClose;

  @override
  State<ProjectScreen> createState() => _ProjectScreenState();
}

class _ProjectScreenState extends State<ProjectScreen> {
  late FuzzmarkProject _project = widget.project;

  Future<void> _openScan() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ScanScreen(
          api: widget.api,
          project: _project,
          onClose: () => Navigator.of(context).pop(),
          onProjectUpdated: (p) => setState(() => _project = p),
        ),
      ),
    );
  }

  Future<void> _openTestBuilder() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => TestBuilderScreen(
          api: widget.api,
          project: _project,
          onClose: () => Navigator.of(context).pop(),
          onProjectUpdated: (p) => setState(() => _project = p),
        ),
      ),
    );
  }

  Future<void> _openRun(String testPath) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => RunScreen(
          api: widget.api,
          project: _project,
          testPath: testPath,
          onClose: () => Navigator.of(context).pop(),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final mono = TextStyle(
      fontFamily: 'monospace',
      fontSize: 13,
      color: Theme.of(context).colorScheme.onSurface,
    );
    final scan = _project.scan;
    final tests = _project.tests;
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: widget.onClose,
        ),
        title: Text(_project.name),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _row(context, 'Base URL', _project.baseUrl, mono: mono),
                const SizedBox(height: 12),
                _row(context, 'File', _project.path, mono: mono),
                const SizedBox(height: 12),
                _row(
                  context,
                  'Scan',
                  scan ?? '(not saved yet)',
                  mono: mono,
                ),
                const SizedBox(height: 24),
                Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  children: [
                    FilledButton.icon(
                      onPressed: _openScan,
                      icon: const Icon(Icons.travel_explore),
                      label: Text(scan == null ? 'Run scan' : 'Re-scan'),
                    ),
                    FilledButton.tonalIcon(
                      onPressed: scan == null ? null : _openTestBuilder,
                      icon: const Icon(Icons.add),
                      label: const Text('New test'),
                    ),
                  ],
                ),
                if (scan == null) ...[
                  const SizedBox(height: 8),
                  Text(
                    'Run a scan first to enable the test builder.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ],
                const SizedBox(height: 24),
                Text(
                  'Tests',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                if (tests.isEmpty)
                  Text(
                    'No tests yet. Use "New test" to build one against a scanned page.',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  )
                else
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: tests
                        .map((t) => ListTile(
                              dense: true,
                              leading: const Icon(Icons.description_outlined),
                              title: Text(t, style: mono),
                              trailing: IconButton(
                                tooltip: 'Run test',
                                icon: const Icon(Icons.play_arrow),
                                onPressed: () => _openRun(t),
                              ),
                              onTap: () => _openRun(t),
                            ))
                        .toList(growable: false),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _row(BuildContext context, String label, String value, {required TextStyle mono}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: Theme.of(context).textTheme.labelMedium),
        const SizedBox(height: 4),
        SelectableText(value, style: mono),
      ],
    );
  }
}
