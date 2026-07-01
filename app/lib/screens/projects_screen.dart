import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/client.dart';
import '../state/providers.dart';
import '../theme/fuzzmark_tokens.dart';
import '../theme/fuzzmark_widgets.dart';

class ProjectsScreen extends ConsumerStatefulWidget {
  const ProjectsScreen({
    super.key,
    required this.onOpen,
  });

  final void Function(FuzzmarkProject) onOpen;

  @override
  ConsumerState<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends ConsumerState<ProjectsScreen> {
  bool _busy = false;

  Future<void> _withBusy(Future<void> Function() body) async {
    setState(() => _busy = true);
    try {
      await body();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _openExisting() => _withBusy(() async {
        final result = await FilePicker.platform.pickFiles(
          dialogTitle: 'Open Fuzzmark project',
          type: FileType.custom,
          allowedExtensions: ['json'],
        );
        final path = result?.files.single.path;
        if (path == null) return;
        await _load(path);
      });

  Future<void> _load(String path) async {
    try {
      final project = await ref.read(apiProvider).loadProject(path);
      await ref.read(recentsProvider).add(project.path);
      if (!mounted) return;
      widget.onOpen(project);
    } on EngineApiException catch (e) {
      _showError(e.message);
    } catch (e) {
      _showError(e.toString());
    }
  }

  Future<void> _forget(String path) async {
    await ref.read(recentsProvider).remove(path);
    if (mounted) setState(() {});
  }

  Future<void> _createNew() async {
    final draft = await showDialog<_NewProjectDraft>(
      context: context,
      builder: (_) => const _NewProjectDialog(),
    );
    if (draft == null) return;
    await _withBusy(() async {
      try {
        final project = await ref.read(apiProvider).initProject(
              path: draft.path,
              name: draft.name,
              baseUrl: draft.baseUrl,
            );
        await ref.read(recentsProvider).add(project.path);
        if (!mounted) return;
        widget.onOpen(project);
      } on EngineApiException catch (e) {
        _showError(e.message);
      }
    });
  }

  void _showError(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    final paths = ref.read(recentsProvider).paths;
    return Scaffold(
      backgroundColor: c.surface0,
      appBar: AppBar(
        backgroundColor: c.surface2,
        foregroundColor: c.textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
        shape: Border(bottom: BorderSide(color: c.border, width: 0.5)),
        title: Text('Fuzzmark', style: FuzzText.title.copyWith(color: c.textPrimary)),
        actions: [
          if (_busy)
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
          constraints: const BoxConstraints(maxWidth: 720),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Projects',
                    style: FuzzText.title
                        .copyWith(color: c.textPrimary, fontSize: 20)),
                const SizedBox(height: 16),
                Row(
                  children: [
                    FilledButton.icon(
                      onPressed: _busy ? null : _createNew,
                      icon: const Icon(Icons.add),
                      label: const Text('New project'),
                    ),
                    const SizedBox(width: 12),
                    OutlinedButton.icon(
                      onPressed: _busy ? null : _openExisting,
                      icon: const Icon(Icons.folder_open),
                      label: const Text('Open project file'),
                    ),
                  ],
                ),
                const SizedBox(height: 32),
                Text('Recent',
                    style: FuzzText.title.copyWith(color: c.textPrimary)),
                const SizedBox(height: FuzzSpace.sm),
                if (paths.isEmpty)
                  FuzzStateCard(
                    kind: FuzzStateKind.empty,
                    title: 'No recent projects',
                    message:
                        'Create a new project or open an existing project.json.',
                    actionLabel: _busy ? null : 'New project',
                    actionIcon: _busy ? null : Icons.add,
                    onAction: _busy ? null : _createNew,
                  )
                else
                  Expanded(
                    child: Container(
                      decoration: BoxDecoration(
                        color: c.surface2,
                        borderRadius:
                            const BorderRadius.all(FuzzSpace.cardRadius),
                        border: Border.all(color: c.border, width: 0.5),
                      ),
                      child: ClipRRect(
                        borderRadius:
                            const BorderRadius.all(FuzzSpace.cardRadius),
                        child: ListView.separated(
                          itemCount: paths.length,
                          separatorBuilder: (_, _) =>
                              Divider(height: 1, color: c.border),
                          itemBuilder: (_, i) {
                            final path = paths[i];
                            return ListTile(
                              leading: Icon(Icons.description_outlined,
                                  color: c.textSecondary),
                              title: Text(
                                _basename(path),
                                style: FuzzText.body
                                    .copyWith(color: c.textPrimary),
                              ),
                              subtitle: Text(
                                path,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: FuzzText.mono
                                    .copyWith(color: c.textMuted),
                              ),
                              trailing: IconButton(
                                icon: Icon(Icons.close, color: c.textMuted),
                                tooltip: 'Forget',
                                onPressed: _busy ? null : () => _forget(path),
                              ),
                              onTap: _busy ? null : () => _load(path),
                            );
                          },
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

String _basename(String path) {
  final i = path.lastIndexOf(RegExp(r'[\\/]'));
  return i < 0 ? path : path.substring(i + 1);
}

class _NewProjectDraft {
  _NewProjectDraft({required this.path, required this.name, required this.baseUrl});
  final String path;
  final String name;
  final String baseUrl;
}

class _NewProjectDialog extends StatefulWidget {
  const _NewProjectDialog();

  @override
  State<_NewProjectDialog> createState() => _NewProjectDialogState();
}

class _NewProjectDialogState extends State<_NewProjectDialog> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _baseUrl = TextEditingController();
  String? _parentDir;

  @override
  void initState() {
    super.initState();
    _name.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _name.dispose();
    _baseUrl.dispose();
    super.dispose();
  }

  Future<void> _chooseParent() async {
    final dir = await FilePicker.platform.getDirectoryPath(
      dialogTitle: 'Choose a parent folder (use "New Folder" to create one)',
    );
    if (dir == null) return;
    setState(() => _parentDir = dir);
  }

  String _slug(String name) {
    final lower = name.trim().toLowerCase();
    final replaced = lower.replaceAll(RegExp(r'[^a-z0-9]+'), '-');
    final trimmed = replaced.replaceAll(RegExp(r'^-+|-+$'), '');
    return trimmed.isEmpty ? 'project' : trimmed;
  }

  String? _projectPath() {
    final parent = _parentDir;
    final name = _name.text.trim();
    if (parent == null || name.isEmpty) return null;
    return '$parent/${_slug(name)}/project.json';
  }

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    final preview = _projectPath();
    return AlertDialog(
      title: const Text('New project'),
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
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'Required' : null,
                autofocus: true,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _baseUrl,
                decoration: const InputDecoration(
                  labelText: 'Base URL',
                  hintText: 'http://localhost:8000/',
                ),
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              Text('Location',
                  style: FuzzText.label.copyWith(color: c.textMuted)),
              const SizedBox(height: 6),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      _parentDir ?? 'No folder chosen',
                      style: FuzzText.mono.copyWith(
                        color: _parentDir == null ? c.textMuted : c.textPrimary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 8),
                  OutlinedButton.icon(
                    onPressed: _chooseParent,
                    icon: const Icon(Icons.folder_open, size: 16),
                    label: Text(_parentDir == null
                        ? 'Choose folder'
                        : 'Change folder'),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              if (preview != null)
                Text(
                  'Will create: $preview',
                  style: FuzzText.caption.copyWith(color: c.textMuted),
                )
              else
                Text(
                  'Pick a parent folder — a subfolder named after the project will be created inside it. Use the folder picker\'s "New Folder" button to create a fresh parent.',
                  style: FuzzText.caption.copyWith(color: c.textMuted),
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
            final path = _projectPath();
            if (path == null) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Choose a parent folder first.')),
              );
              return;
            }
            Navigator.of(context).pop(_NewProjectDraft(
              path: path,
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
