import 'package:flutter/material.dart';

import '../api/client.dart';
import 'scan_screen.dart';

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

  @override
  Widget build(BuildContext context) {
    final mono = TextStyle(
      fontFamily: 'monospace',
      fontSize: 13,
      color: Theme.of(context).colorScheme.onSurface,
    );
    final scan = _project.scan;
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
                Row(
                  children: [
                    FilledButton.icon(
                      onPressed: _openScan,
                      icon: const Icon(Icons.travel_explore),
                      label: Text(scan == null ? 'Run scan' : 'Re-scan'),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                Text(
                  'Test builder, run, and review will land in the next Phase 5 commits.',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
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
