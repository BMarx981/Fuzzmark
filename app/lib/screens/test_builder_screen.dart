import 'package:flutter/material.dart';

import '../api/client.dart';

class TestBuilderScreen extends StatefulWidget {
  const TestBuilderScreen({
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
  State<TestBuilderScreen> createState() => _TestBuilderScreenState();
}

class _TestBuilderScreenState extends State<TestBuilderScreen> {
  List<ScannedPage>? _pages;
  ScannedPage? _selectedPage;
  bool _loadingPages = false;
  bool _extracting = false;
  bool _saving = false;
  String? _error;

  List<ExtractedField> _fields = const [];
  Map<String, List<FieldSuggestion>> _suggestions = const {};
  final Map<String, TextEditingController> _values = {};

  @override
  void initState() {
    super.initState();
    _loadPages();
  }

  @override
  void dispose() {
    for (final c in _values.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _loadPages() async {
    setState(() {
      _loadingPages = true;
      _error = null;
    });
    try {
      final pages = await widget.api.listScannedPages(widget.project.path);
      if (!mounted) return;
      setState(() => _pages = pages);
    } on EngineApiException catch (e) {
      _setError(e.message);
    } catch (e) {
      _setError(e.toString());
    } finally {
      if (mounted) setState(() => _loadingPages = false);
    }
  }

  Future<void> _pickPage(ScannedPage page) async {
    setState(() {
      _selectedPage = page;
      _extracting = true;
      _fields = const [];
      _suggestions = const {};
      _error = null;
      for (final c in _values.values) {
        c.dispose();
      }
      _values.clear();
    });
    try {
      final fields = await widget.api.extractFields(
        projectPath: widget.project.path,
        url: page.url,
      );
      final suggestions = fields.isEmpty
          ? <String, List<FieldSuggestion>>{}
          : await widget.api.suggestFields(
              projectPath: widget.project.path,
              fields: fields,
            );
      if (!mounted) return;
      setState(() {
        _fields = fields;
        _suggestions = suggestions;
        for (final f in fields) {
          _values[f.selector] = TextEditingController();
        }
      });
    } on EngineApiException catch (e) {
      _setError(e.message);
    } catch (e) {
      _setError(e.toString());
    } finally {
      if (mounted) setState(() => _extracting = false);
    }
  }

  Future<void> _saveTest() async {
    final page = _selectedPage;
    if (page == null) return;
    final filled = _filledFields();
    if (filled.isEmpty) {
      _showSnack('Fill at least one field before saving');
      return;
    }
    final draft = await showDialog<_SaveTestDraft>(
      context: context,
      builder: (_) => _SaveTestDialog(initialName: _defaultName(page)),
    );
    if (draft == null) return;
    final captureName = draft.captureName.isEmpty ? 'after-fill' : draft.captureName;
    final test = {
      'name': draft.name,
      'flow': [
        {'kind': 'visit', 'url': page.url},
        for (final entry in filled.entries)
          {'kind': 'fill', 'selector': entry.key, 'value': entry.value},
        {'kind': 'capture', 'name': captureName},
      ],
    };
    setState(() => _saving = true);
    try {
      final updated = await widget.api.saveTest(
        projectPath: widget.project.path,
        test: test,
        filename: draft.filename.isEmpty ? null : draft.filename,
      );
      if (!mounted) return;
      widget.onProjectUpdated(updated);
      _showSnack('Saved "${draft.name}" to the project');
      Navigator.of(context).pop();
    } on EngineApiException catch (e) {
      _setError(e.message);
    } catch (e) {
      _setError(e.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Map<String, String> _filledFields() {
    final out = <String, String>{};
    for (final f in _fields) {
      final v = _values[f.selector]?.text ?? '';
      if (v.isNotEmpty) out[f.selector] = v;
    }
    return out;
  }

  String _defaultName(ScannedPage page) {
    final uri = Uri.tryParse(page.url);
    final segments =
        uri?.pathSegments.where((s) => s.isNotEmpty).toList() ?? const <String>[];
    final slug = segments.isEmpty ? 'home' : segments.last;
    return '$slug-smoke';
  }

  void _setError(String message) {
    if (!mounted) return;
    setState(() => _error = message);
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final busy = _loadingPages || _extracting || _saving;
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: busy ? null : widget.onClose,
        ),
        title: Text('New test — ${widget.project.name}'),
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
      body: Column(
        children: [
          if (_error != null)
            Container(
              width: double.infinity,
              color: Theme.of(context).colorScheme.errorContainer,
              padding: const EdgeInsets.all(12),
              child: Text(
                _error!,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.onErrorContainer,
                ),
              ),
            ),
          Expanded(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SizedBox(width: 320, child: _pagesPane(context)),
                const VerticalDivider(width: 1),
                Expanded(child: _fieldsPane(context)),
              ],
            ),
          ),
          _footer(context),
        ],
      ),
    );
  }

  Widget _pagesPane(BuildContext context) {
    if (_loadingPages) {
      return const Center(child: CircularProgressIndicator());
    }
    final pages = _pages;
    if (pages == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            'Failed to load pages.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ),
      );
    }
    if (pages.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            'No pages in the saved scan. Run a scan first.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ),
      );
    }
    return ListView.separated(
      itemCount: pages.length,
      separatorBuilder: (_, _) => const Divider(height: 1),
      itemBuilder: (_, i) {
        final p = pages[i];
        final selected = identical(_selectedPage, p) ||
            (_selectedPage != null && _selectedPage!.url == p.url);
        return ListTile(
          dense: true,
          selected: selected,
          leading: Text(
            'd${p.depth}',
            style: Theme.of(context).textTheme.labelSmall,
          ),
          title: Text(
            p.title?.isNotEmpty == true ? p.title! : p.url,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          subtitle: Text(
            p.url,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
          ),
          enabled: !_extracting && !_saving,
          onTap: () => _pickPage(p),
        );
      },
    );
  }

  Widget _fieldsPane(BuildContext context) {
    if (_extracting) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_selectedPage == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            'Pick a page on the left to extract its form fields.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        ),
      );
    }
    if (_fields.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            'No interactive form fields found on this page.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: _fields.length,
      separatorBuilder: (_, _) => const SizedBox(height: 12),
      itemBuilder: (_, i) => _fieldCard(_fields[i]),
    );
  }

  Widget _fieldCard(ExtractedField field) {
    final controller = _values[field.selector]!;
    final suggestions = _suggestions[field.selector] ?? const <FieldSuggestion>[];
    final label = field.label?.isNotEmpty == true
        ? field.label!
        : field.name?.isNotEmpty == true
            ? field.name!
            : field.selector;
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    label,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Text(
                  '${field.kind}${field.type != null ? "/${field.type}" : ""}',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 2),
            Text(
              field.selector,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: controller,
              enabled: !_saving,
              decoration: InputDecoration(
                isDense: true,
                border: const OutlineInputBorder(),
                hintText: field.validation.required ? 'required' : 'value',
                suffixIcon: controller.text.isEmpty
                    ? null
                    : IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () => setState(() => controller.clear()),
                      ),
              ),
              onChanged: (_) => setState(() {}),
            ),
            if (suggestions.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: suggestions
                    .map((s) => _chip(s, controller))
                    .toList(growable: false),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _chip(FieldSuggestion s, TextEditingController controller) {
    final color = _categoryColor(s.category);
    return ActionChip(
      visualDensity: VisualDensity.compact,
      tooltip: '${s.category}\n${s.label}',
      backgroundColor: color.background,
      side: BorderSide(color: color.border),
      label: Text(
        s.label,
        style: TextStyle(color: color.foreground, fontSize: 12),
      ),
      onPressed: _saving
          ? null
          : () => setState(() {
                controller.text = s.value;
                controller.selection = TextSelection.collapsed(
                  offset: controller.text.length,
                );
              }),
    );
  }

  Widget _footer(BuildContext context) {
    final filledCount = _filledFields().length;
    return Container(
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(color: Theme.of(context).dividerColor),
        ),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          Text(
            _selectedPage == null
                ? 'Pick a page to begin.'
                : '$filledCount of ${_fields.length} fields filled',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const Spacer(),
          FilledButton.icon(
            onPressed: _saving || filledCount == 0 ? null : _saveTest,
            icon: const Icon(Icons.save),
            label: const Text('Save test'),
          ),
        ],
      ),
    );
  }

  _ChipColors _categoryColor(String category) {
    final scheme = Theme.of(context).colorScheme;
    switch (category) {
      case 'security':
        return _ChipColors(
          background: scheme.errorContainer,
          foreground: scheme.onErrorContainer,
          border: scheme.error,
        );
      case 'boundary':
        return _ChipColors(
          background: scheme.tertiaryContainer,
          foreground: scheme.onTertiaryContainer,
          border: scheme.tertiary,
        );
      case 'empty':
        return _ChipColors(
          background: scheme.surfaceContainerHighest,
          foreground: scheme.onSurface,
          border: scheme.outlineVariant,
        );
      case 'format-invalid':
        return _ChipColors(
          background: scheme.errorContainer.withValues(alpha: 0.5),
          foreground: scheme.onErrorContainer,
          border: scheme.error.withValues(alpha: 0.5),
        );
      case 'format-valid':
        return _ChipColors(
          background: scheme.primaryContainer,
          foreground: scheme.onPrimaryContainer,
          border: scheme.primary,
        );
      case 'i18n':
        return _ChipColors(
          background: scheme.secondaryContainer,
          foreground: scheme.onSecondaryContainer,
          border: scheme.secondary,
        );
      default:
        return _ChipColors(
          background: scheme.surfaceContainerHighest,
          foreground: scheme.onSurface,
          border: scheme.outlineVariant,
        );
    }
  }
}

class _ChipColors {
  _ChipColors({
    required this.background,
    required this.foreground,
    required this.border,
  });

  final Color background;
  final Color foreground;
  final Color border;
}

class _SaveTestDraft {
  _SaveTestDraft({
    required this.name,
    required this.filename,
    required this.captureName,
  });

  final String name;
  final String filename;
  final String captureName;
}

class _SaveTestDialog extends StatefulWidget {
  const _SaveTestDialog({required this.initialName});

  final String initialName;

  @override
  State<_SaveTestDialog> createState() => _SaveTestDialogState();
}

class _SaveTestDialogState extends State<_SaveTestDialog> {
  late final TextEditingController _name =
      TextEditingController(text: widget.initialName);
  late final TextEditingController _capture =
      TextEditingController(text: 'after-fill');
  final TextEditingController _filename = TextEditingController();
  final _form = GlobalKey<FormState>();

  @override
  void dispose() {
    _name.dispose();
    _filename.dispose();
    _capture.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Save test'),
      content: SizedBox(
        width: 460,
        child: Form(
          key: _form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                controller: _name,
                autofocus: true,
                decoration: const InputDecoration(labelText: 'Test name'),
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'Required' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _capture,
                decoration: const InputDecoration(labelText: 'Capture name'),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _filename,
                decoration: const InputDecoration(
                  labelText: 'Filename (optional)',
                  hintText: 'tests/<name>.json',
                ),
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
            Navigator.of(context).pop(_SaveTestDraft(
              name: _name.text.trim(),
              filename: _filename.text.trim(),
              captureName: _capture.text.trim(),
            ));
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}
