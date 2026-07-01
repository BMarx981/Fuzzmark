import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/client.dart';
import '../state/run_controller.dart';
import '../theme/fuzzmark_tokens.dart';
import '../theme/fuzzmark_widgets.dart';
import 'report_screen.dart';

class RunScreen extends ConsumerStatefulWidget {
  const RunScreen({
    super.key,
    required this.project,
    required this.testPath,
    required this.onClose,
  });

  final FuzzmarkProject project;
  final String testPath;
  final VoidCallback onClose;

  @override
  ConsumerState<RunScreen> createState() => _RunScreenState();
}

class _RunScreenState extends ConsumerState<RunScreen> {
  bool _headed = true;

  RunJobKey get _key => (
        projectPath: widget.project.path,
        testRelativePath: widget.testPath,
      );

  Future<void> _run() =>
      ref.read(runControllerProvider(_key).notifier).start(headed: _headed);

  Future<void> _cancel() =>
      ref.read(runControllerProvider(_key).notifier).cancel();

  Future<void> _openReport() async {
    final result = ref.read(runControllerProvider(_key)).result;
    if (result == null) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ReportScreen(
          project: widget.project,
          runResult: result,
          onClose: () => Navigator.of(context).pop(),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    final state = ref.watch(runControllerProvider(_key));
    final busy = state.isBusy;
    final result = state.result;
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
        title: Text('Run — ${widget.testPath}',
            style: FuzzText.title.copyWith(color: c.textPrimary)),
        actions: [
          if (busy)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                    strokeWidth: 2, color: c.accentFill),
              ),
            ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 960),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(widget.project.name,
                              style: FuzzText.title
                                  .copyWith(color: c.textPrimary)),
                          const SizedBox(height: 2),
                          Text(widget.testPath,
                              style: FuzzText.mono
                                  .copyWith(color: c.textSecondary)),
                        ],
                      ),
                    ),
                    Row(
                      children: [
                        Tooltip(
                          message: _headed
                              ? 'A visible Chromium window opens so you can '
                                  'watch the run. Clicks are slowed slightly '
                                  'so they are easy to follow.'
                              : 'The run is headless — faster, but you cannot '
                                  'see what is happening.',
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                _headed
                                    ? Icons.visibility
                                    : Icons.visibility_off,
                                size: 16,
                                color: c.textSecondary,
                              ),
                              const SizedBox(width: 6),
                              Text('Watch run',
                                  style: FuzzText.label
                                      .copyWith(color: c.textSecondary)),
                            ],
                          ),
                        ),
                        Switch(
                          value: _headed,
                          onChanged:
                              busy ? null : (v) => setState(() => _headed = v),
                        ),
                        const SizedBox(width: 12),
                        if (busy)
                          OutlinedButton.icon(
                            onPressed: state.handle == null ? null : _cancel,
                            icon: const Icon(Icons.stop_circle_outlined),
                            label: const Text('Cancel'),
                          ),
                        if (!busy && result != null) ...[
                          OutlinedButton.icon(
                            onPressed: _openReport,
                            icon: const Icon(Icons.assessment_outlined),
                            label: const Text('View report'),
                          ),
                          const SizedBox(width: 8),
                        ],
                        if (!busy)
                          FilledButton.icon(
                            onPressed: _run,
                            icon: const Icon(Icons.play_arrow),
                            label: Text(
                                result == null ? 'Run test' : 'Re-run'),
                          ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                if (busy) _progressBar(context, state),
                if (state.errorMessage != null) ...[
                  const SizedBox(height: FuzzSpace.sm),
                  FuzzErrorBanner(message: state.errorMessage!),
                ],
                if (state.phase == RunPhase.cancelled) ...[
                  const SizedBox(height: FuzzSpace.sm),
                  _statusBanner(
                    context,
                    icon: Icons.stop_circle_outlined,
                    text: 'Run cancelled',
                  ),
                ],
                const SizedBox(height: 12),
                Expanded(child: _resultBody(context, state)),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _progressBar(BuildContext context, RunState state) {
    final c = context.fuzz;
    final total = state.totalSteps;
    final done = state.stepsDone;
    final progress = total > 0 ? done / total : null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LinearProgressIndicator(
          value: progress,
          minHeight: 4,
          backgroundColor: c.surface1,
          valueColor: AlwaysStoppedAnimation(c.accentFill),
        ),
        const SizedBox(height: 4),
        Text(
          total > 0
              ? 'Step $done/$total'
              : (state.phase == RunPhase.starting
                  ? 'Starting run…'
                  : 'Running…'),
          style: FuzzText.caption.copyWith(color: c.textMuted),
        ),
      ],
    );
  }

  Widget _resultBody(BuildContext context, RunState state) {
    if (state.phase == RunPhase.idle) {
      return FuzzStateCard(
        kind: FuzzStateKind.empty,
        title: 'No run yet',
        message:
            'Press “Run test” to execute the flow and capture screenshots.',
        actionLabel: 'Run test',
        actionIcon: Icons.play_arrow,
        onAction: _run,
      );
    }
    if (state.isBusy && state.captures.isEmpty) {
      return FuzzStateCard(
        kind: FuzzStateKind.loading,
        title: state.phase == RunPhase.starting
            ? 'Starting fuzzmark engine job…'
            : 'Driving the browser…',
        message: 'Running the test flow against the page.',
      );
    }
    return _LiveResultView(state: state);
  }
}

Widget _statusBanner(BuildContext context,
    {required IconData icon, required String text}) {
  final c = context.fuzz;
  return Container(
    padding: const EdgeInsets.symmetric(
        horizontal: FuzzSpace.md, vertical: FuzzSpace.sm),
    decoration: BoxDecoration(
      color: c.surface2,
      borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
      border: Border.all(color: c.border, width: 0.5),
    ),
    child: Row(
      children: [
        Icon(icon, size: 18, color: c.textSecondary),
        const SizedBox(width: 8),
        Text(text, style: FuzzText.body.copyWith(color: c.textPrimary)),
      ],
    ),
  );
}

class _LiveResultView extends StatelessWidget {
  const _LiveResultView({required this.state});

  final RunState state;

  bool get _hasErrors =>
      state.consoleErrors.isNotEmpty ||
      state.pageErrors.isNotEmpty ||
      state.failedRequests.isNotEmpty;

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    final captures = state.captures;
    final result = state.result;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Text('${captures.length} captures',
                style: FuzzText.body.copyWith(color: c.textPrimary)),
            const SizedBox(width: 16),
            if (_hasErrors)
              _pill(context, _errorSummary(),
                  bg: c.dangerBg, fg: c.dangerText)
            else if (state.isTerminal)
              _pill(context, 'no errors collected',
                  bg: c.surface1, fg: c.textMuted),
            const Spacer(),
            if (result != null)
              Flexible(
                child: Text(
                  result.runDir,
                  style: FuzzText.mono.copyWith(color: c.textMuted),
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.right,
                ),
              ),
          ],
        ),
        const SizedBox(height: FuzzSpace.md),
        Expanded(
          child: ListView(
            children: [
              for (final cap in captures) _CaptureTile(capture: cap),
              if (_hasErrors) ...[
                const SizedBox(height: 8),
                _ErrorsPanel(state: state),
              ],
            ],
          ),
        ),
      ],
    );
  }

  String _errorSummary() {
    final parts = <String>[];
    if (state.consoleErrors.isNotEmpty) {
      parts.add('${state.consoleErrors.length} console');
    }
    if (state.pageErrors.isNotEmpty) {
      parts.add('${state.pageErrors.length} page');
    }
    if (state.failedRequests.isNotEmpty) {
      parts.add('${state.failedRequests.length} request');
    }
    return parts.join(' · ');
  }
}

Widget _pill(BuildContext context, String text,
    {required Color bg, required Color fg}) {
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
    decoration: BoxDecoration(
      color: bg,
      borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
    ),
    child: Text(text,
        style: FuzzText.caption
            .copyWith(color: fg, fontWeight: FontWeight.w500)),
  );
}

class _CaptureTile extends StatelessWidget {
  const _CaptureTile({required this.capture});

  final RunCapture capture;

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    final file = File(capture.screenshotPath);
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
              Text(capture.name,
                  style: FuzzText.heading.copyWith(color: c.textPrimary)),
              const SizedBox(width: 8),
              Text(
                'step ${capture.stepIndex}'
                '${capture.viewport != null ? " · ${capture.viewport}" : ""}',
                style: FuzzText.caption.copyWith(color: c.textMuted),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            capture.screenshotPath,
            style: FuzzText.mono.copyWith(color: c.textMuted, fontSize: 11),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 8),
          if (file.existsSync())
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: Image.file(
                file,
                fit: BoxFit.fitWidth,
                errorBuilder: (_, _, _) => Text(
                  'Failed to render screenshot',
                  style: FuzzText.body.copyWith(color: c.dangerText),
                ),
              ),
            )
          else
            Text(
              'screenshot not found on disk',
              style: FuzzText.body.copyWith(color: c.dangerText),
            ),
        ],
      ),
    );
  }
}

class _ErrorsPanel extends StatelessWidget {
  const _ErrorsPanel({required this.state});

  final RunState state;

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
          if (state.consoleErrors.isNotEmpty) ...[
            Text('Console',
                style: FuzzText.label.copyWith(color: c.textMuted)),
            for (final m in state.consoleErrors)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text('[${m.level}] ${m.text}',
                    style: FuzzText.mono.copyWith(color: c.textPrimary)),
              ),
            const SizedBox(height: 8),
          ],
          if (state.pageErrors.isNotEmpty) ...[
            Text('Page errors',
                style: FuzzText.label.copyWith(color: c.textMuted)),
            for (final e in state.pageErrors)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text(e,
                    style: FuzzText.mono.copyWith(color: c.textPrimary)),
              ),
            const SizedBox(height: 8),
          ],
          if (state.failedRequests.isNotEmpty) ...[
            Text('Failed requests',
                style: FuzzText.label.copyWith(color: c.textMuted)),
            for (final r in state.failedRequests)
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
