import 'dart:io';

import 'package:flutter/material.dart';

import '../api/client.dart';
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
    final mono = const TextStyle(fontFamily: 'monospace', fontSize: 13);
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: _running ? null : widget.onClose,
        ),
        title: Text('Run — ${widget.testPath}'),
        actions: [
          if (_running)
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
                              style: Theme.of(context).textTheme.titleMedium),
                          const SizedBox(height: 2),
                          Text(widget.testPath, style: mono),
                        ],
                      ),
                    ),
                    Row(
                      children: [
                        const Text('Headed'),
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
                if (_running) const LinearProgressIndicator(),
                if (_error != null) ...[
                  const SizedBox(height: 8),
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
      return Center(
        child: Text(
          'Driving the browser…',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
      );
    }
    final result = _result;
    if (result == null) {
      return Center(
        child: Text(
          'Press “Run test” to execute the flow and capture screenshots.',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
      );
    }
    return _ResultView(result: result);
  }
}

class _ResultView extends StatelessWidget {
  const _ResultView({required this.result});

  final RunResult result;

  @override
  Widget build(BuildContext context) {
    final mono = const TextStyle(fontFamily: 'monospace', fontSize: 12);
    final scheme = Theme.of(context).colorScheme;
    final captures = result.captures;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Text('${captures.length} captures',
                style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(width: 16),
            if (result.hasErrors)
              Chip(
                label: Text(
                  _errorSummary(result),
                  style: TextStyle(color: scheme.onErrorContainer),
                ),
                backgroundColor: scheme.errorContainer,
                side: BorderSide.none,
              )
            else
              Chip(
                label: const Text('no errors collected'),
                backgroundColor: scheme.surfaceContainerHighest,
                side: BorderSide.none,
              ),
            const Spacer(),
            Text(
              result.runDir,
              style: mono,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
        const Divider(height: 16),
        Expanded(
          child: ListView(
            children: [
              for (final c in captures) _CaptureTile(capture: c),
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

class _CaptureTile extends StatelessWidget {
  const _CaptureTile({required this.capture});

  final RunCapture capture;

  @override
  Widget build(BuildContext context) {
    final file = File(capture.screenshotPath);
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  capture.name,
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                const SizedBox(width: 8),
                Text(
                  'step ${capture.stepIndex}'
                  '${capture.viewport != null ? " · ${capture.viewport}" : ""}',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              capture.screenshotPath,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
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
                  errorBuilder: (_, _, _) =>
                      const Text('Failed to render screenshot'),
                ),
              )
            else
              Text(
                'screenshot not found on disk',
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      ),
    );
  }
}

class _ErrorsPanel extends StatelessWidget {
  const _ErrorsPanel({required this.result});

  final RunResult result;

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
            if (result.consoleErrors.isNotEmpty) ...[
              Text('Console',
                  style: Theme.of(context).textTheme.labelMedium),
              for (final m in result.consoleErrors)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Text('[${m.level}] ${m.text}', style: mono),
                ),
              const SizedBox(height: 8),
            ],
            if (result.pageErrors.isNotEmpty) ...[
              Text('Page errors',
                  style: Theme.of(context).textTheme.labelMedium),
              for (final e in result.pageErrors)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Text(e, style: mono),
                ),
              const SizedBox(height: 8),
            ],
            if (result.failedRequests.isNotEmpty) ...[
              Text('Failed requests',
                  style: Theme.of(context).textTheme.labelMedium),
              for (final r in result.failedRequests)
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
