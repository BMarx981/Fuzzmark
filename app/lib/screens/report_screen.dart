import 'dart:io';

import 'package:flutter/material.dart';

import '../api/client.dart';
import '../theme/fuzzmark_tokens.dart';
import '../theme/fuzzmark_widgets.dart';
import 'diff_viewer.dart';

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
  final Set<String> _verdictFilter = <String>{};

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
    final c = context.fuzz;
    final busy = _loading || _approving;
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
          onPressed: busy ? null : widget.onClose,
        ),
        title: Text('Report — ${widget.runResult.testName}',
            style: FuzzText.title.copyWith(color: c.textPrimary)),
        actions: [
          if (busy)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2, color: c.accentFill),
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
                if (_error != null) ...[
                  _errorBanner(context, _error!),
                  const SizedBox(height: FuzzSpace.sm),
                ],
                if (_loading)
                  LinearProgressIndicator(
                    minHeight: 4,
                    backgroundColor: c.surface1,
                    valueColor: AlwaysStoppedAnimation(c.accentFill),
                  ),
                Expanded(child: _body(context)),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _body(BuildContext context) {
    final c = context.fuzz;
    final report = _report;
    if (report == null) {
      if (_loading) {
        return const FuzzStateCard(
          kind: FuzzStateKind.loading,
          title: 'Rendering report…',
          message: 'Reading captures and computing diffs.',
        );
      }
      return const FuzzStateCard(
        kind: FuzzStateKind.error,
        title: 'Report not available',
        message: 'The engine did not return a report for this run.',
      );
    }
    final allSorted = [...report.entries]
      ..sort((a, b) => _sortKey(a).compareTo(_sortKey(b)));
    final entries = _verdictFilter.isEmpty
        ? allSorted
        : allSorted.where((e) => _verdictFilter.contains(e.verdict)).toList();
    final canApprove = report.baselinesDir != null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _summary(context, report),
        const SizedBox(height: FuzzSpace.sm),
        Row(
          children: [
            Expanded(
              child: Text(
                report.baselinesDir == null
                    ? 'No baselines path configured — approvals disabled.'
                    : 'Baselines: ${report.baselinesDir}',
                style: FuzzText.mono.copyWith(color: c.textMuted),
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
        const SizedBox(height: FuzzSpace.md),
        Expanded(
          child: entries.isEmpty
              ? Center(
                  child: Text(
                    'No entries match the active filter.',
                    style: FuzzText.body.copyWith(color: c.textMuted),
                  ),
                )
              : ListView(
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
    final c = context.fuzz;
    final counts = report.verdictCounts;
    final keys = counts.keys.toList()
      ..sort((a, b) =>
          (_verdictOrder[a] ?? 99).compareTo(_verdictOrder[b] ?? 99));
    return Wrap(
      spacing: 8,
      runSpacing: 4,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        for (final k in keys)
          _verdictToggleChip(
            context,
            k,
            counts[k]!,
            selected: _verdictFilter.contains(k),
            anyFilterActive: _verdictFilter.isNotEmpty,
            onToggle: () {
              setState(() {
                if (!_verdictFilter.add(k)) _verdictFilter.remove(k);
              });
            },
          ),
        if (_verdictFilter.isNotEmpty)
          TextButton.icon(
            onPressed: () => setState(_verdictFilter.clear),
            icon: const Icon(Icons.filter_alt_off, size: 14),
            label: Text(
              'Clear filter',
              style: FuzzText.label.copyWith(color: c.textSecondary),
            ),
          ),
      ],
    );
  }
}

Widget _errorBanner(BuildContext context, String message) =>
    FuzzErrorBanner(message: message);

({Color bg, Color fg}) _verdictPalette(BuildContext context, String verdict) {
  final c = context.fuzz;
  switch (verdict) {
    case 'pass':
      return (bg: c.successBg, fg: c.successText);
    case 'size-shift':
    case 'content-change':
      return (bg: c.warningBg, fg: c.warningText);
    case 'layout-break':
    case 'error':
      return (bg: c.dangerBg, fg: c.dangerText);
    case 'no-baseline':
    default:
      return (bg: c.surface1, fg: c.textMuted);
  }
}

Widget _verdictChip(BuildContext context, String verdict, int count) {
  final p = _verdictPalette(context, verdict);
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
    decoration: BoxDecoration(
      color: p.bg,
      borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
    ),
    child: Text(
      '$verdict $count',
      style: FuzzText.caption
          .copyWith(color: p.fg, fontWeight: FontWeight.w500),
    ),
  );
}

Widget _verdictToggleChip(
  BuildContext context,
  String verdict,
  int count, {
  required bool selected,
  required bool anyFilterActive,
  required VoidCallback onToggle,
}) {
  final c = context.fuzz;
  final p = _verdictPalette(context, verdict);
  final dimmed = anyFilterActive && !selected;
  return Material(
    color: Colors.transparent,
    borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
    child: InkWell(
      onTap: onToggle,
      borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
        decoration: BoxDecoration(
          color: dimmed ? c.surface1 : p.bg,
          borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
          border: selected
              ? Border.all(color: p.fg, width: 1.2)
              : Border.all(color: Colors.transparent, width: 1.2),
        ),
        child: Text(
          '$verdict $count',
          style: FuzzText.caption.copyWith(
            color: dimmed ? c.textMuted : p.fg,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    ),
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
    final c = context.fuzz;
    final score = entry.score;
    final threshold = entry.threshold;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(FuzzSpace.md),
      decoration: BoxDecoration(
        color: c.surface2,
        borderRadius: const BorderRadius.all(FuzzSpace.cardRadius),
        border: Border.all(color: c.border, width: 0.5),
      ),
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
                  style: FuzzText.heading.copyWith(color: c.textPrimary),
                ),
              ),
              Text(
                'step ${entry.stepIndex}'
                '${entry.viewport != null ? " · ${entry.viewport}" : ""}'
                '${score != null ? " · ssim ${score.toStringAsFixed(4)}" : ""}'
                '${threshold != null ? " / ${threshold.toStringAsFixed(4)}" : ""}',
                style: FuzzText.caption.copyWith(color: c.textMuted),
              ),
              const SizedBox(width: 8),
              TextButton.icon(
                onPressed: () => _openViewer(context, DiffViewerMode.sideBySide),
                icon: const Icon(Icons.open_in_full, size: 14),
                label: const Text('Open viewer'),
              ),
              const SizedBox(width: 4),
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
    );
  }

  void _openViewer(BuildContext context, DiffViewerMode mode) {
    showDiffViewer(
      context,
      title: entry.name,
      baselinePath: entry.baselinePath,
      capturePath: entry.capturePath,
      diffPath: entry.diffPath,
      initialMode: mode,
    );
  }

  Widget _diffRow(BuildContext context) {
    final panels = <Widget>[
      _imagePanel(context,
          label: 'Baseline',
          path: entry.baselinePath,
          onTap: () => _openViewer(context, DiffViewerMode.sideBySide)),
      _imagePanel(context,
          label: 'Capture',
          path: entry.capturePath,
          onTap: () => _openViewer(context,
              entry.baselinePath != null
                  ? DiffViewerMode.slider
                  : DiffViewerMode.sideBySide)),
    ];
    if (entry.diffPath != null) {
      panels.add(_imagePanel(context,
          label: 'Diff',
          path: entry.diffPath,
          onTap: () => _openViewer(context, DiffViewerMode.diffOnly)));
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
      {required String label,
      required String? path,
      required VoidCallback onTap}) {
    final c = context.fuzz;
    Widget body;
    if (path == null) {
      body = Container(
        height: 120,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: c.surface1,
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(
          'no baseline',
          style: FuzzText.caption.copyWith(color: c.textMuted),
        ),
      );
    } else if (!File(path).existsSync()) {
      body = Container(
        height: 120,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: c.surface1,
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(
          'file missing',
          style: FuzzText.caption.copyWith(color: c.dangerText),
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
        Text(label, style: FuzzText.label.copyWith(color: c.textMuted)),
        const SizedBox(height: 4),
        MouseRegion(
          cursor: SystemMouseCursors.click,
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: onTap,
            child: body,
          ),
        ),
      ],
    );
  }
}

class _ErrorsPanel extends StatelessWidget {
  const _ErrorsPanel({required this.report});

  final RunReport report;

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    return Container(
      padding: const EdgeInsets.all(FuzzSpace.md),
      decoration: BoxDecoration(
        color: c.surface2,
        borderRadius: const BorderRadius.all(FuzzSpace.cardRadius),
        border: Border.all(color: c.border, width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Collected errors',
              style: FuzzText.heading.copyWith(color: c.textPrimary)),
          const SizedBox(height: FuzzSpace.sm),
          if (report.consoleErrors.isNotEmpty) ...[
            Text('Console',
                style: FuzzText.label.copyWith(color: c.textMuted)),
            for (final m in report.consoleErrors)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text('[${m.level}] ${m.text}',
                    style: FuzzText.mono.copyWith(color: c.textPrimary)),
              ),
            const SizedBox(height: 8),
          ],
          if (report.pageErrors.isNotEmpty) ...[
            Text('Page errors',
                style: FuzzText.label.copyWith(color: c.textMuted)),
            for (final e in report.pageErrors)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text(e,
                    style: FuzzText.mono.copyWith(color: c.textPrimary)),
              ),
            const SizedBox(height: 8),
          ],
          if (report.failedRequests.isNotEmpty) ...[
            Text('Failed requests',
                style: FuzzText.label.copyWith(color: c.textMuted)),
            for (final r in report.failedRequests)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text(
                  '${r.method} ${r.url}'
                  '${r.status != null ? " → ${r.status}" : ""}'
                  '${r.failure != null ? " (${r.failure})" : ""}',
                  style: FuzzText.mono.copyWith(color: c.textPrimary),
                ),
              ),
          ],
        ],
      ),
    );
  }
}
