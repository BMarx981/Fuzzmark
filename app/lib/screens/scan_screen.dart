import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../api/client.dart';
import '../theme/fuzzmark_tokens.dart';
import '../theme/fuzzmark_widgets.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({
    super.key,
    required this.api,
    required this.project,
    required this.onClose,
    required this.onProjectUpdated,
    required this.onSwitchProject,
  });

  final FuzzmarkApi api;
  final FuzzmarkProject project;
  final VoidCallback onClose;
  final ValueChanged<FuzzmarkProject> onProjectUpdated;
  final Future<void> Function(FuzzmarkProject) onSwitchProject;

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final _maxDepth = TextEditingController(text: '3');
  final _maxPages = TextEditingController(text: '50');
  final _rateLimit = TextEditingController(text: '0.0');
  late final TextEditingController _baseUrl =
      TextEditingController(text: widget.project.baseUrl);
  late String _persistedBaseUrl = widget.project.baseUrl;
  bool _ignoreRobots = false;
  bool _allowCrossOrigin = false;
  bool _showBounds = false;

  bool _scanning = false;
  bool _saving = false;
  String? _error;
  ScanResult? _result;
  final Set<String> _selected = <String>{};

  @override
  void dispose() {
    _maxDepth.dispose();
    _maxPages.dispose();
    _rateLimit.dispose();
    _baseUrl.dispose();
    super.dispose();
  }

  CrawlBoundsRequest? _readBounds() {
    final depth = int.tryParse(_maxDepth.text.trim());
    final pages = int.tryParse(_maxPages.text.trim());
    final rate = double.tryParse(_rateLimit.text.trim());
    if (depth == null || depth < 0) {
      _showError('Max depth must be a non-negative integer');
      return null;
    }
    if (pages == null || pages <= 0) {
      _showError('Max pages must be a positive integer');
      return null;
    }
    if (rate == null || rate < 0) {
      _showError('Rate limit must be a non-negative number');
      return null;
    }
    return CrawlBoundsRequest(
      maxDepth: depth,
      maxPages: pages,
      rateLimit: rate,
      ignoreRobots: _ignoreRobots,
      allowCrossOrigin: _allowCrossOrigin,
    );
  }

  Future<void> _runScan() async {
    final bounds = _readBounds();
    if (bounds == null) return;
    final url = _baseUrl.text.trim();
    if (url.isEmpty) {
      _showError('Base URL must not be empty');
      return;
    }
    setState(() {
      _scanning = true;
      _error = null;
      _result = null;
      _selected.clear();
    });
    try {
      if (url != _persistedBaseUrl) {
        final updated = await widget.api.setBaseUrl(
          projectPath: widget.project.path,
          baseUrl: url,
        );
        if (!mounted) return;
        widget.onProjectUpdated(updated);
        setState(() => _persistedBaseUrl = updated.baseUrl);
      }
      final result = await widget.api.runScan(
        projectPath: widget.project.path,
        bounds: bounds,
      );
      if (!mounted) return;
      setState(() {
        _result = result;
        _selected
          ..clear()
          ..addAll(result.pages.where((p) => p.error == null).map((p) => p.url));
      });
    } on EngineApiException catch (e) {
      _setError(e.message);
    } catch (e) {
      _setError(e.toString());
    } finally {
      if (mounted) setState(() => _scanning = false);
    }
  }

  Future<void> _saveSelection() async {
    final result = _result;
    if (result == null) return;
    if (_selected.isEmpty) {
      _showError('Select at least one page before saving');
      return;
    }
    setState(() => _saving = true);
    final filtered = _filteredSiteMap(result, _selected);
    try {
      final updated = await widget.api.saveScan(
        projectPath: widget.project.path,
        siteMap: filtered,
      );
      if (!mounted) return;
      widget.onProjectUpdated(updated);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Saved ${_selected.length} pages to scan.json')),
      );
    } on EngineApiException catch (e) {
      _setError(e.message);
    } catch (e) {
      _setError(e.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _saveAsNewProject() async {
    final draft = await showDialog<_SaveAsDraft>(
      context: context,
      builder: (_) => _SaveAsDialog(
        initialName: widget.project.name,
        initialBaseUrl: _baseUrl.text.trim().isEmpty
            ? widget.project.baseUrl
            : _baseUrl.text.trim(),
      ),
    );
    if (draft == null) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final created = await widget.api.initProject(
        path: draft.path,
        name: draft.name,
        baseUrl: draft.baseUrl,
      );
      if (!mounted) return;
      await widget.onSwitchProject(created);
    } on EngineApiException catch (e) {
      _setError(e.message);
    } catch (e) {
      _setError(e.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _setError(String message) {
    if (!mounted) return;
    setState(() => _error = message);
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  void _toggleAll(bool value) {
    final result = _result;
    if (result == null) return;
    setState(() {
      _selected.clear();
      if (value) {
        for (final p in result.pages) {
          if (p.error == null) _selected.add(p.url);
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    final busy = _scanning || _saving;
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
        title: Text('Scan — ${widget.project.name}',
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
          constraints: const BoxConstraints(maxWidth: 840),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _header(context),
                const SizedBox(height: 12),
                _boundsPanel(context),
                const SizedBox(height: 12),
                if (_error != null) ...[
                  _errorBanner(context, _error!),
                  const SizedBox(height: FuzzSpace.sm),
                ],
                if (_scanning)
                  LinearProgressIndicator(
                    minHeight: 4,
                    backgroundColor: c.surface1,
                    valueColor: AlwaysStoppedAnimation(c.accentFill),
                  ),
                Expanded(child: _results(context)),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _header(BuildContext context) {
    final c = context.fuzz;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextField(
                controller: _baseUrl,
                enabled: !(_scanning || _saving),
                decoration: const InputDecoration(
                  labelText: 'Base URL',
                  isDense: true,
                ),
                style: FuzzText.mono.copyWith(color: c.textPrimary),
                keyboardType: TextInputType.url,
                autocorrect: false,
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: 4),
              Text(
                _baseUrl.text.trim() == _persistedBaseUrl
                    ? 'Crawl the project base URL to discover pages.'
                    : 'URL will be saved to the project when you start the scan.',
                style: FuzzText.caption.copyWith(color: c.textMuted),
              ),
            ],
          ),
        ),
        const SizedBox(width: 12),
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              FilledButton.icon(
                onPressed: (_scanning || _saving) ? null : _runScan,
                icon: const Icon(Icons.travel_explore),
                label: Text(_result == null ? 'Start scan' : 'Re-scan'),
              ),
              if (_baseUrl.text.trim() != _persistedBaseUrl) ...[
                const SizedBox(height: 6),
                TextButton.icon(
                  onPressed: (_scanning || _saving) ? null : _saveAsNewProject,
                  icon: const Icon(Icons.save_as, size: 18),
                  label: const Text('Save as new project…'),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _boundsPanel(BuildContext context) {
    final c = context.fuzz;
    return Container(
      decoration: BoxDecoration(
        color: c.surface2,
        borderRadius: const BorderRadius.all(FuzzSpace.cardRadius),
        border: Border.all(color: c.border, width: 0.5),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          initiallyExpanded: _showBounds,
          onExpansionChanged: (v) => setState(() => _showBounds = v),
          tilePadding: const EdgeInsets.symmetric(horizontal: 16),
          collapsedIconColor: c.textSecondary,
          iconColor: c.textSecondary,
          title: Text('Crawl bounds',
              style: FuzzText.heading.copyWith(color: c.textPrimary)),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(
              'depth ${_maxDepth.text} · pages ${_maxPages.text}'
              '${_ignoreRobots ? " · ignore robots" : ""}'
              '${_allowCrossOrigin ? " · cross-origin" : ""}',
              style: FuzzText.caption.copyWith(color: c.textMuted),
            ),
          ),
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _maxDepth,
                          decoration: const InputDecoration(labelText: 'Max depth'),
                          keyboardType: TextInputType.number,
                          onChanged: (_) => setState(() {}),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: TextField(
                          controller: _maxPages,
                          decoration: const InputDecoration(labelText: 'Max pages'),
                          keyboardType: TextInputType.number,
                          onChanged: (_) => setState(() {}),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: TextField(
                          controller: _rateLimit,
                          decoration:
                              const InputDecoration(labelText: 'Rate limit (s)'),
                          keyboardType: TextInputType.number,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    controlAffinity: ListTileControlAffinity.leading,
                    dense: true,
                    value: _ignoreRobots,
                    title: Text('Ignore robots.txt',
                        style:
                            FuzzText.body.copyWith(color: c.textPrimary)),
                    onChanged: (v) => setState(() => _ignoreRobots = v ?? false),
                  ),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    controlAffinity: ListTileControlAffinity.leading,
                    dense: true,
                    value: _allowCrossOrigin,
                    title: Text('Allow cross-origin links',
                        style:
                            FuzzText.body.copyWith(color: c.textPrimary)),
                    onChanged: (v) =>
                        setState(() => _allowCrossOrigin = v ?? false),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _results(BuildContext context) {
    final c = context.fuzz;
    final result = _result;
    if (result == null) {
      if (_scanning) {
        return const FuzzStateCard(
          kind: FuzzStateKind.loading,
          title: 'Crawling…',
          message: 'Discovering pages from the base URL.',
        );
      }
      return FuzzStateCard(
        kind: FuzzStateKind.empty,
        title: 'No scan yet',
        message: 'Adjust crawl bounds and start a scan.',
        actionLabel: 'Start scan',
        actionIcon: Icons.travel_explore,
        onAction: _runScan,
      );
    }
    final allSelected = result.pages
        .where((p) => p.error == null)
        .every((p) => _selected.contains(p.url));
    final anySelected = _selected.isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Checkbox(
              tristate: true,
              value: allSelected
                  ? true
                  : anySelected
                      ? null
                      : false,
              onChanged: _saving ? null : (v) => _toggleAll(v ?? false),
            ),
            const SizedBox(width: 4),
            Text(
              '${_selected.length} of ${result.pages.length} pages selected'
              '${result.skipped.isNotEmpty ? " · ${result.skipped.length} skipped" : ""}',
              style: FuzzText.body.copyWith(color: c.textPrimary),
            ),
            const Spacer(),
            FilledButton.icon(
              onPressed: _saving || _selected.isEmpty ? null : _saveSelection,
              icon: const Icon(Icons.save),
              label: const Text('Save scan.json'),
            ),
          ],
        ),
        const SizedBox(height: FuzzSpace.md),
        Expanded(
          child: Container(
            decoration: BoxDecoration(
              color: c.surface2,
              borderRadius: const BorderRadius.all(FuzzSpace.cardRadius),
              border: Border.all(color: c.border, width: 0.5),
            ),
            child: ClipRRect(
              borderRadius: const BorderRadius.all(FuzzSpace.cardRadius),
              child: ListView.separated(
                itemCount: result.pages.length + result.skipped.length,
                separatorBuilder: (_, _) => Divider(height: 1, color: c.border),
                itemBuilder: (_, i) {
                  if (i < result.pages.length) {
                    return _pageTile(result.pages[i]);
                  }
                  return _skipTile(result.skipped[i - result.pages.length]);
                },
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _pageTile(ScannedPage page) {
    final c = context.fuzz;
    final hasError = page.error != null;
    return CheckboxListTile(
      controlAffinity: ListTileControlAffinity.leading,
      dense: true,
      value: _selected.contains(page.url),
      onChanged: hasError || _saving
          ? null
          : (v) {
              setState(() {
                if (v == true) {
                  _selected.add(page.url);
                } else {
                  _selected.remove(page.url);
                }
              });
            },
      title: Text(
        page.title?.isNotEmpty == true ? page.title! : page.url,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: FuzzText.body.copyWith(color: c.textPrimary),
      ),
      subtitle: Text(
        hasError ? 'error: ${page.error}' : page.url,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: FuzzText.mono
            .copyWith(color: hasError ? c.dangerText : c.textMuted),
      ),
      secondary: Text(
        'd${page.depth}',
        style: FuzzText.caption.copyWith(color: c.textMuted),
      ),
    );
  }

  Widget _skipTile(ScannedSkip skip) {
    final c = context.fuzz;
    return ListTile(
      dense: true,
      leading: Icon(Icons.block, size: 18, color: c.textMuted),
      title: Text(
        skip.url,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: FuzzText.mono.copyWith(color: c.textSecondary),
      ),
      subtitle: Text(
        'skipped — ${skip.reason}',
        style: FuzzText.caption.copyWith(color: c.textMuted),
      ),
    );
  }
}

Widget _errorBanner(BuildContext context, String message) =>
    FuzzErrorBanner(message: message);

class _SaveAsDraft {
  _SaveAsDraft({required this.path, required this.name, required this.baseUrl});
  final String path;
  final String name;
  final String baseUrl;
}

class _SaveAsDialog extends StatefulWidget {
  const _SaveAsDialog({required this.initialName, required this.initialBaseUrl});

  final String initialName;
  final String initialBaseUrl;

  @override
  State<_SaveAsDialog> createState() => _SaveAsDialogState();
}

class _SaveAsDialogState extends State<_SaveAsDialog> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: widget.initialName);
  late final _baseUrl = TextEditingController(text: widget.initialBaseUrl);
  final _parentDir = TextEditingController();
  final _folderName = TextEditingController();
  final _filename = TextEditingController(text: 'project.json');

  @override
  void dispose() {
    _name.dispose();
    _baseUrl.dispose();
    _parentDir.dispose();
    _folderName.dispose();
    _filename.dispose();
    super.dispose();
  }

  Future<void> _chooseParent() async {
    final dir = await FilePicker.platform.getDirectoryPath(
      dialogTitle: 'Choose a parent folder',
    );
    if (dir == null) return;
    setState(() => _parentDir.text = dir);
  }

  String? _validateNotEmpty(String? v) =>
      (v == null || v.trim().isEmpty) ? 'Required' : null;

  String? _validateSegment(String? v) {
    if (v == null || v.trim().isEmpty) return 'Required';
    final t = v.trim();
    if (t.contains('/') || t.contains('\\')) return 'No slashes';
    return null;
  }

  String get _computedPath {
    final parent = _parentDir.text.trim();
    final folder = _folderName.text.trim();
    final file = _filename.text.trim();
    if (parent.isEmpty || folder.isEmpty || file.isEmpty) return '';
    final sep = parent.endsWith('/') || parent.endsWith('\\') ? '' : '/';
    return '$parent$sep$folder/$file';
  }

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    return AlertDialog(
      title: const Text('Save as new project'),
      content: SizedBox(
        width: 520,
        child: Form(
          key: _form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                controller: _name,
                decoration: const InputDecoration(labelText: 'Name'),
                validator: _validateNotEmpty,
                autofocus: true,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _baseUrl,
                decoration: const InputDecoration(labelText: 'Base URL'),
                validator: _validateNotEmpty,
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _parentDir,
                      decoration: const InputDecoration(
                        labelText: 'Parent folder',
                        hintText: '/path/to/parent',
                      ),
                      validator: _validateNotEmpty,
                      onChanged: (_) => setState(() {}),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: const Icon(Icons.folder_open),
                    tooltip: 'Choose parent folder',
                    onPressed: _chooseParent,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _folderName,
                      decoration: const InputDecoration(
                        labelText: 'New folder name',
                        hintText: 'my-project',
                      ),
                      validator: _validateSegment,
                      onChanged: (_) => setState(() {}),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      controller: _filename,
                      decoration: const InputDecoration(labelText: 'File name'),
                      validator: _validateSegment,
                      onChanged: (_) => setState(() {}),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                _computedPath.isEmpty
                    ? 'The folder will be created if it does not exist.'
                    : _computedPath,
                style: FuzzText.mono.copyWith(color: c.textMuted),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () {
            if (!_form.currentState!.validate()) return;
            Navigator.of(context).pop(_SaveAsDraft(
              path: _computedPath,
              name: _name.text.trim(),
              baseUrl: _baseUrl.text.trim(),
            ));
          },
          child: const Text('Create'),
        ),
      ],
    );
  }
}

Map<String, dynamic> _filteredSiteMap(ScanResult result, Set<String> keep) {
  final raw = Map<String, dynamic>.from(result.raw);
  final pages = (raw['pages'] as List? ?? [])
      .whereType<Map>()
      .where((p) => keep.contains(p['url']))
      .map((p) => Map<String, dynamic>.from(p))
      .toList();
  raw['pages'] = pages;
  raw['page_count'] = pages.length;
  return raw;
}
