import 'package:flutter/material.dart';

import '../api/client.dart';

class ProjectScreen extends StatelessWidget {
  const ProjectScreen({super.key, required this.project, required this.onClose});

  final FuzzmarkProject project;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    final mono = TextStyle(
      fontFamily: 'monospace',
      fontSize: 13,
      color: Theme.of(context).colorScheme.onSurface,
    );
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: onClose,
        ),
        title: Text(project.name),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _row(context, 'Base URL', project.baseUrl, mono: mono),
                const SizedBox(height: 12),
                _row(context, 'File', project.path, mono: mono),
                const SizedBox(height: 32),
                Text(
                  'Scan, test builder, run, and review will land in the next Phase 5 commits.',
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
