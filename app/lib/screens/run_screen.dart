import 'dart:io';

import 'package:flutter/material.dart';

import '../api/client.dart';
import '../theme/fuzzmark_tokens.dart';
import '../theme/fuzzmark_widgets.dart';
import 'report_screen.dart';

class RunScreen extends StatefulWidget {
  const RunScreen({
    super.key,
    required this.api,
    required this.project,
    required this.testPath,
    required this.onClose,
  });

  final FuzzmarkApi api;
  final FuzzmarkProject project;
  final String testPath;
  final VoidCallback onClose;

  @override
  State<RunScreen> createState() => _RunScreenState();
}

class _RunScreenState extends State<RunScreen> {
  bool _running = false;
  bool _headed = false;
  String? _error;
  RunResult? _result;

  Future<void> _run() async {
    setState(() {
      _running = true;
      _error = null;
      _result = null;
    });
    try {
      final result = await widget.api.runTest(
        projectPath: widget.project.path,
        testRelativePath: widget.testPath,
        headed: _headed,
      );
      if (!mounted) return;
      setState(() => _result = result);
    } on EngineApiException catch (e) {
      _setError(e.message);
    } catch (e) {
      _setError(e.toString());
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  void _setError(String message) {
    if (!mounted) return;
    setState(() => _error = message);
  }

  Future<void> _openReport() async {
    final result = _result;
    if (result == null) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ReportScreen(
          api: widget.api,
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
          onPressed: _running ? null : widget.onClose,
        ),
        title: Text('Run — ${widget.testPath}',
            style: FuzzText.title.copyWith(color: c.textPrimary)),
        actions: [
          if (_running)
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
                        Text('Headed',
                            style:
                                FuzzText.label.copyWith(color: c.textSecondary)),
                        Switch(
                          value: _headed,
                          onChanged: _running
                              ? null
                              : (v) => setState(() => _headed = v),
                        ),
                        const SizedBox(width: 12),
                        if (_result != null)
                          OutlinedButton.icon(
                            onPressed: _running ? null : _openReport,
                            icon: const Icon(Icons.assessment_outlined),
                            label: const Text('View report'),
                          ),
                        if (_result != null) const SizedBox(width: 8),
                        FilledButton.icon(
                          onPressed: _running ? null : _run,
                          icon: const Icon(Icons.play_arrow),
                          label: Text(_result == null ? 'Run test' : 'Re-run'),
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                if (_running)
                  LinearProgressIndicator(
                    minHeight: 4,
                    backgroundColor: c.surface1,
                    valueColor: AlwaysStoppedAnimation(c.accentFill),
                  ),
                if (_error != null) ...[
                  const SizedBox(height: FuzzSpace.sm),
                  _errorBanner(context, _error!),
                ],
                const SizedBox(height: 12),
                Expanded(child: _resultBody(context)),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _resultBody(BuildContext context) {
    if (_running && _result == null) {
      return const FuzzStateCard(
        kind: FuzzStateKind.loading,
        title: 'Driving the browser…',
        message: 'Running the test flow against the page.',
      );
    }
    final result = _result;
    if (result == null) {
      return FuzzStateCard(
        kind: FuzzStateKind.empty,
        title: 'No run yet',
        message: 'Press “Run test” to execute the flow and capture screenshots.',
        actionLabel: 'Run test',
        actionIcon: Icons.play_arrow,
        onAction: _run,
      );
    }
    return _ResultView(result: result);
  }
}

Widget _errorBanner(BuildContext context, String message) {
  final c = context.fuzz;
  return Container(
    padding: const EdgeInsets.all(FuzzSpace.md),
    decoration: BoxDecoration(
      color: c.dangerBg,
      borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
      border: Border.all(color: c.border, width: 0.5),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.error_outline, size: 16, color: c.dangerText),
        const SizedBox(width: FuzzSpace.sm),
        Expanded(
          child: Text(message,
              style: FuzzText.body.copyWith(color: c.dangerText)),
        ),
      ],
    ),
  );
}

class _ResultView extends StatelessWidget {
  const _ResultView({required this.result});

  final RunResult result;

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    final captures = result.captures;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Text('${captures.length} captures',
                style: FuzzText.body.copyWith(color: c.textPrimary)),
            const SizedBox(width: 16),
            if (result.hasErrors)
              _pill(context, _errorSummary(result),
                  bg: c.dangerBg, fg: c.dangerText)
            else
              _pill(context, 'no errors collected',
                  bg: c.surface1, fg: c.textMuted),
            const Spacer(),
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
              if (result.hasErrors) ...[
                const SizedBox(height: 8),
                _ErrorsPanel(result: result),
              ],
            ],
          ),
        ),
      ],
    );
  }

  String _errorSummary(RunResult r) {
    final parts = <String>[];
    if (r.consoleErrors.isNotEmpty) {
      parts.add('${r.consoleErrors.length} console');
    }
    if (r.pageErrors.isNotEmpty) parts.add('${r.pageErrors.length} page');
    if (r.failedRequests.isNotEmpty) {
      parts.add('${r.failedRequests.length} request');
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
  const _ErrorsPanel({required this.result});

  final RunResult result;

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
          if (result.consoleErrors.isNotEmpty) ...[
            Text('Console',
                style: FuzzText.label.copyWith(color: c.textMuted)),
            for (final m in result.consoleErrors)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text('[${m.level}] ${m.text}',
                    style: FuzzText.mono.copyWith(color: c.textPrimary)),
              ),
            const SizedBox(height: 8),
          ],
          if (result.pageErrors.isNotEmpty) ...[
            Text('Page errors',
                style: FuzzText.label.copyWith(color: c.textMuted)),
            for (final e in result.pageErrors)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text(e,
                    style: FuzzText.mono.copyWith(color: c.textPrimary)),
              ),
            const SizedBox(height: 8),
          ],
          if (result.failedRequests.isNotEmpty) ...[
            Text('Failed requests',
                style: FuzzText.label.copyWith(color: c.textMuted)),
            for (final r in result.failedRequests)
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
