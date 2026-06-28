import 'package:flutter/material.dart';

import '../api/client.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({
    super.key,
    required this.api,
    required this.project,
    required this.onClose,
    required this.onProjectUpdated,
  });

  final FuzzmarkApi api;
  final FuzzmarkProject project;
  final VoidCallback onClose;
  final ValueChanged<FuzzmarkProject> onProjectUpdated;

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final _maxDepth = TextEditingController(text: '3');
  final _maxPages = TextEditingController(text: '50');
  final _rateLimit = TextEditingController(text: '0.0');
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
    setState(() {
      _scanning = true;
      _error = null;
      _result = null;
      _selected.clear();
    });
    try {
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
    final busy = _scanning || _saving;
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: busy ? null : widget.onClose,
        ),
        title: Text('Scan — ${widget.project.name}'),
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
                if (_scanning) const LinearProgressIndicator(),
                Expanded(child: _results(context)),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _header(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.project.baseUrl,
                style: const TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                'Crawl the project base URL to discover pages.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
            ],
          ),
        ),
        FilledButton.icon(
          onPressed: (_scanning || _saving) ? null : _runScan,
          icon: const Icon(Icons.travel_explore),
          label: Text(_result == null ? 'Start scan' : 'Re-scan'),
        ),
      ],
    );
  }

  Widget _boundsPanel(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: ExpansionTile(
        initiallyExpanded: _showBounds,
        onExpansionChanged: (v) => setState(() => _showBounds = v),
        title: const Text('Crawl bounds'),
        subtitle: Text(
          'depth ${_maxDepth.text} · pages ${_maxPages.text}'
          '${_ignoreRobots ? " · ignore robots" : ""}'
          '${_allowCrossOrigin ? " · cross-origin" : ""}',
          style: Theme.of(context).textTheme.bodySmall,
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
                  title: const Text('Ignore robots.txt'),
                  onChanged: (v) => setState(() => _ignoreRobots = v ?? false),
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  controlAffinity: ListTileControlAffinity.leading,
                  dense: true,
                  value: _allowCrossOrigin,
                  title: const Text('Allow cross-origin links'),
                  onChanged: (v) =>
                      setState(() => _allowCrossOrigin = v ?? false),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _results(BuildContext context) {
    final result = _result;
    if (result == null) {
      return Center(
        child: Text(
          _scanning
              ? 'Crawling…'
              : 'No scan yet. Adjust crawl bounds and start a scan.',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
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
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const Spacer(),
            FilledButton.icon(
              onPressed: _saving || _selected.isEmpty ? null : _saveSelection,
              icon: const Icon(Icons.save),
              label: const Text('Save scan.json'),
            ),
          ],
        ),
        const Divider(height: 16),
        Expanded(
          child: ListView.separated(
            itemCount: result.pages.length + result.skipped.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (_, i) {
              if (i < result.pages.length) {
                return _pageTile(result.pages[i]);
              }
              return _skipTile(result.skipped[i - result.pages.length]);
            },
          ),
        ),
      ],
    );
  }

  Widget _pageTile(ScannedPage page) {
    final hasError = page.error != null;
    final scheme = Theme.of(context).colorScheme;
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
      ),
      subtitle: Text(
        hasError ? 'error: ${page.error}' : page.url,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          fontFamily: 'monospace',
          fontSize: 12,
          color: hasError ? scheme.error : scheme.onSurfaceVariant,
        ),
      ),
      secondary: Text(
        'd${page.depth}',
        style: Theme.of(context).textTheme.labelSmall,
      ),
    );
  }

  Widget _skipTile(ScannedSkip skip) {
    final scheme = Theme.of(context).colorScheme;
    return ListTile(
      dense: true,
      leading: Icon(Icons.block, size: 18, color: scheme.onSurfaceVariant),
      title: Text(
        skip.url,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
      ),
      subtitle: Text(
        'skipped — ${skip.reason}',
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: scheme.onSurfaceVariant,
            ),
      ),
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
