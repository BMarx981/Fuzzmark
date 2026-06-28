import 'dart:io';

import 'package:flutter/material.dart';

import '../api/client.dart';

const _verdictOrder = {
  'layout-break': 0,
  'content-change': 1,
  'size-shift': 2,
  'no-baseline': 3,
  'error': 4,
  'pass': 5,
};

class ReportScreen extends StatefulWidget {
  const ReportScreen({
    super.key,
    required this.api,
    required this.project,
    required this.runResult,
    required this.onClose,
  });

  final FuzzmarkApi api;
  final FuzzmarkProject project;
  final RunResult runResult;
  final VoidCallback onClose;

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  bool _loading = true;
  bool _approving = false;
  String? _error;
  RunReport? _report;
  final Set<String> _selected = <String>{};

  @override
  void initState() {
    super.initState();
    _renderReport();
  }

  Future<void> _renderReport() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final report = await widget.api.reportTest(
        projectPath: widget.project.path,
        result: widget.runResult.raw,
      );
      if (!mounted) return;
      setState(() {
        _report = report;
        _selected
          ..clear()
          ..addAll(report.entries
              .where((e) => e.verdict != 'pass')
              .map((e) => e.name));
      });
    } on EngineApiException catch (e) {
      _setError(e.message);
    } catch (e) {
      _setError(e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _approveSelected() async {
    final report = _report;
    if (report == null || _selected.isEmpty) return;
    setState(() => _approving = true);
    try {
      final res = await widget.api.approveBaselines(
        projectPath: widget.project.path,
        result: widget.runResult.raw,
        captureNames: _selected.toList(growable: false),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Approved ${res.written.length} captures'
            '${res.skipped.isNotEmpty ? " · ${res.skipped.length} skipped" : ""}',
          ),
        ),
      );
      await _renderReport();
    } on EngineApiException catch (e) {
      _setError(e.message);
    } catch (e) {
      _setError(e.toString());
    } finally {
      if (mounted) setState(() => _approving = false);
    }
  }

  void _setError(String m) {
    if (!mounted) return;
    setState(() => _error = m);
  }

  @override
  Widget build(BuildContext context) {
    final busy = _loading || _approving;
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: busy ? null : widget.onClose,
        ),
        title: Text('Report — ${widget.runResult.testName}'),
        actions: [
          if (busy)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1100),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (_error != null)
                  Card(
                    color: Theme.of(context).colorScheme.errorContainer,
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text(
                        _error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.onErrorContainer,
                        ),
                      ),
                    ),
                  ),
                if (_loading) const LinearProgressIndicator(),
                Expanded(child: _body(context)),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _body(BuildContext context) {
    final report = _report;
    if (report == null) {
      return Center(
        child: Text(
          _loading ? 'Rendering report…' : 'Report not available.',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
      );
    }
    final entries = [...report.entries]
      ..sort((a, b) => _sortKey(a).compareTo(_sortKey(b)));
    final canApprove = report.baselinesDir != null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _summary(context, report),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: Text(
                report.baselinesDir == null
                    ? 'No baselines path configured — approvals disabled.'
                    : 'Baselines: ${report.baselinesDir}',
                style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(width: 12),
            FilledButton.icon(
              onPressed: !canApprove || _approving || _selected.isEmpty
                  ? null
                  : _approveSelected,
              icon: const Icon(Icons.check),
              label: Text('Approve ${_selected.length}'),
            ),
          ],
        ),
        const Divider(height: 16),
        Expanded(
          child: ListView(
            children: [
              for (final e in entries)
                _EntryCard(
                  entry: e,
                  selected: _selected.contains(e.name),
                  approveEnabled: canApprove && !_approving,
                  onSelected: (v) {
                    setState(() {
                      if (v) {
                        _selected.add(e.name);
                      } else {
                        _selected.remove(e.name);
                      }
                    });
                  },
                ),
              if (report.hasErrors) ...[
                const SizedBox(height: 8),
                _ErrorsPanel(report: report),
              ],
            ],
          ),
        ),
      ],
    );
  }

  int _sortKey(ReportEntry e) =>
      (_verdictOrder[e.verdict] ?? 99) * 1000 + e.stepIndex;

  Widget _summary(BuildContext context, RunReport report) {
    final counts = report.verdictCounts;
    final keys = counts.keys.toList()
      ..sort((a, b) =>
          (_verdictOrder[a] ?? 99).compareTo(_verdictOrder[b] ?? 99));
    return Wrap(
      spacing: 8,
      runSpacing: 4,
      children: [
        for (final k in keys) _verdictChip(context, k, counts[k]!),
      ],
    );
  }
}

Color _verdictColor(BuildContext context, String verdict) {
  final scheme = Theme.of(context).colorScheme;
  switch (verdict) {
    case 'pass':
      return scheme.primaryContainer;
    case 'size-shift':
      return scheme.tertiaryContainer;
    case 'content-change':
      return scheme.secondaryContainer;
    case 'layout-break':
      return scheme.errorContainer;
    case 'no-baseline':
      return scheme.surfaceContainerHighest;
    case 'error':
      return scheme.errorContainer;
  }
  return scheme.surfaceContainerHighest;
}

Color _verdictOn(BuildContext context, String verdict) {
  final scheme = Theme.of(context).colorScheme;
  switch (verdict) {
    case 'pass':
      return scheme.onPrimaryContainer;
    case 'size-shift':
      return scheme.onTertiaryContainer;
    case 'content-change':
      return scheme.onSecondaryContainer;
    case 'layout-break':
      return scheme.onErrorContainer;
    case 'no-baseline':
      return scheme.onSurfaceVariant;
    case 'error':
      return scheme.onErrorContainer;
  }
  return scheme.onSurfaceVariant;
}

Widget _verdictChip(BuildContext context, String verdict, int count) {
  return Chip(
    label: Text(
      '$verdict $count',
      style: TextStyle(color: _verdictOn(context, verdict)),
    ),
    backgroundColor: _verdictColor(context, verdict),
    side: BorderSide.none,
  );
}

class _EntryCard extends StatelessWidget {
  const _EntryCard({
    required this.entry,
    required this.selected,
    required this.approveEnabled,
    required this.onSelected,
  });

  final ReportEntry entry;
  final bool selected;
  final bool approveEnabled;
  final ValueChanged<bool> onSelected;

  @override
  Widget build(BuildContext context) {
    final score = entry.score;
    final threshold = entry.threshold;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _verdictChip(context, entry.verdict, 1),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    entry.name,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Text(
                  'step ${entry.stepIndex}'
                  '${entry.viewport != null ? " · ${entry.viewport}" : ""}'
                  '${score != null ? " · ssim ${score.toStringAsFixed(4)}" : ""}'
                  '${threshold != null ? " / ${threshold.toStringAsFixed(4)}" : ""}',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
                const SizedBox(width: 8),
                FilterChip(
                  selected: selected,
                  label: const Text('Approve'),
                  onSelected: approveEnabled ? onSelected : null,
                ),
              ],
            ),
            const SizedBox(height: 8),
            _diffRow(context),
          ],
        ),
      ),
    );
  }

  Widget _diffRow(BuildContext context) {
    final panels = <Widget>[
      _imagePanel(context, label: 'Baseline', path: entry.baselinePath),
      _imagePanel(context, label: 'Capture', path: entry.capturePath),
    ];
    if (entry.diffPath != null) {
      panels.add(_imagePanel(context, label: 'Diff', path: entry.diffPath));
    }
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < panels.length; i++) ...[
          Expanded(child: panels[i]),
          if (i < panels.length - 1) const SizedBox(width: 8),
        ],
      ],
    );
  }

  Widget _imagePanel(BuildContext context,
      {required String label, required String? path}) {
    final scheme = Theme.of(context).colorScheme;
    Widget body;
    if (path == null) {
      body = Container(
        height: 120,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: scheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(
          'no baseline',
          style: TextStyle(color: scheme.onSurfaceVariant),
        ),
      );
    } else if (!File(path).existsSync()) {
      body = Container(
        height: 120,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: scheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(
          'file missing',
          style: TextStyle(color: scheme.error),
        ),
      );
    } else {
      body = ClipRRect(
        borderRadius: BorderRadius.circular(4),
        child: Image.file(File(path), fit: BoxFit.fitWidth),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: Theme.of(context).textTheme.labelMedium),
        const SizedBox(height: 4),
        body,
      ],
    );
  }
}

class _ErrorsPanel extends StatelessWidget {
  const _ErrorsPanel({required this.report});

  final RunReport report;

  @override
  Widget build(BuildContext context) {
    final mono = const TextStyle(fontFamily: 'monospace', fontSize: 12);
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Collected errors',
                style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            if (report.consoleErrors.isNotEmpty) ...[
              Text('Console', style: Theme.of(context).textTheme.labelMedium),
              for (final m in report.consoleErrors)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Text('[${m.level}] ${m.text}', style: mono),
                ),
              const SizedBox(height: 8),
            ],
            if (report.pageErrors.isNotEmpty) ...[
              Text('Page errors',
                  style: Theme.of(context).textTheme.labelMedium),
              for (final e in report.pageErrors)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Text(e, style: mono),
                ),
              const SizedBox(height: 8),
            ],
            if (report.failedRequests.isNotEmpty) ...[
              Text('Failed requests',
                  style: Theme.of(context).textTheme.labelMedium),
              for (final r in report.failedRequests)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Text(
                    '${r.method} ${r.url}'
                    '${r.status != null ? " → ${r.status}" : ""}'
                    '${r.failure != null ? " (${r.failure})" : ""}',
                    style: mono,
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }
}
