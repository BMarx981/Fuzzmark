import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/client.dart';
import '../theme/fuzzmark_tokens.dart';
import '../theme/fuzzmark_widgets.dart';
import 'run_screen.dart';
import 'scan_screen.dart';
import 'test_builder_screen.dart';

class ProjectScreen extends ConsumerStatefulWidget {
  const ProjectScreen({
    super.key,
    required this.project,
    required this.onClose,
    required this.onSwitchProject,
  });

  final FuzzmarkProject project;
  final VoidCallback onClose;
  final Future<void> Function(FuzzmarkProject) onSwitchProject;

  @override
  ConsumerState<ProjectScreen> createState() => _ProjectScreenState();
}

class _ProjectScreenState extends ConsumerState<ProjectScreen> {
  late FuzzmarkProject _project = widget.project;

  Future<void> _openScan() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ScanScreen(
          project: _project,
          onClose: () => Navigator.of(context).pop(),
          onProjectUpdated: (p) => setState(() => _project = p),
          onSwitchProject: widget.onSwitchProject,
        ),
      ),
    );
  }

  Future<void> _openTestBuilder() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => TestBuilderScreen(
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
          project: _project,
          testPath: testPath,
          onClose: () => Navigator.of(context).pop(),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    final scan = _project.scan;
    final tests = _project.tests;
    return Scaffold(
      backgroundColor: c.surface0,
      appBar: AppBar(
        backgroundColor: c.surface2,
        foregroundColor: c.textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
        shape: Border(bottom: BorderSide(color: c.border, width: 0.5)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: widget.onClose,
        ),
        title: Text(_project.name, style: FuzzText.title.copyWith(color: c.textPrimary)),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Container(
                  padding: const EdgeInsets.all(FuzzSpace.lg),
                  decoration: BoxDecoration(
                    color: c.surface2,
                    borderRadius: const BorderRadius.all(FuzzSpace.cardRadius),
                    border: Border.all(color: c.border, width: 0.5),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _row(context, 'Base URL', _project.baseUrl),
                      const SizedBox(height: FuzzSpace.md),
                      _row(context, 'File', _project.path),
                      const SizedBox(height: FuzzSpace.md),
                      _row(context, 'Scan', scan ?? '(not saved yet)'),
                    ],
                  ),
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
                  const SizedBox(height: FuzzSpace.sm),
                  Text(
                    'Run a scan first to enable the test builder.',
                    style: FuzzText.caption.copyWith(color: c.textMuted),
                  ),
                ],
                const SizedBox(height: 24),
                Text('Tests', style: FuzzText.title.copyWith(color: c.textPrimary)),
                const SizedBox(height: FuzzSpace.sm),
                if (tests.isEmpty)
                  FuzzStateCard(
                    kind: FuzzStateKind.empty,
                    title: 'No tests yet',
                    message: 'Use "New test" to build one against a scanned page.',
                    actionLabel: scan == null ? null : 'New test',
                    actionIcon: scan == null ? null : Icons.add,
                    onAction: scan == null ? null : _openTestBuilder,
                  )
                else
                  Container(
                    decoration: BoxDecoration(
                      color: c.surface2,
                      borderRadius: const BorderRadius.all(FuzzSpace.cardRadius),
                      border: Border.all(color: c.border, width: 0.5),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        FuzzTableRow(
                          header: true,
                          cells: const [
                            FuzzCell(Text('Test'), flex: 5),
                            FuzzCell(Text(''), flex: 1),
                          ],
                        ),
                        for (final t in tests)
                          FuzzTableRow(
                            cells: [
                              FuzzCell(
                                InkWell(
                                  onTap: () => _openRun(t),
                                  child: Row(
                                    children: [
                                      Icon(Icons.description_outlined, size: 16, color: c.textSecondary),
                                      const SizedBox(width: FuzzSpace.sm),
                                      Expanded(
                                        child: Text(t, style: FuzzText.mono.copyWith(color: c.textPrimary)),
                                      ),
                                    ],
                                  ),
                                ),
                                flex: 5,
                              ),
                              FuzzCell(
                                Align(
                                  alignment: Alignment.centerRight,
                                  child: IconButton(
                                    tooltip: 'Run test',
                                    icon: Icon(Icons.play_arrow, color: c.accentText),
                                    onPressed: () => _openRun(t),
                                  ),
                                ),
                                flex: 1,
                              ),
                            ],
                          ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _row(BuildContext context, String label, String value) {
    final c = context.fuzz;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: FuzzText.label.copyWith(color: c.textMuted)),
        const SizedBox(height: 4),
        SelectableText(value, style: FuzzText.mono.copyWith(color: c.textPrimary)),
      ],
    );
  }
}
