import 'dart:io';

import 'package:flutter/material.dart';

import '../theme/fuzzmark_tokens.dart';

enum DiffViewerMode { sideBySide, slider, diffOnly }

Future<void> showDiffViewer(
  BuildContext context, {
  required String title,
  required String? baselinePath,
  required String? capturePath,
  required String? diffPath,
  DiffViewerMode initialMode = DiffViewerMode.sideBySide,
}) {
  final start = initialMode == DiffViewerMode.slider && baselinePath == null
      ? DiffViewerMode.sideBySide
      : initialMode == DiffViewerMode.diffOnly && diffPath == null
          ? DiffViewerMode.sideBySide
          : initialMode;
  return showDialog<void>(
    context: context,
    barrierDismissible: true,
    barrierColor: Colors.black.withValues(alpha: 0.65),
    builder: (_) => _DiffViewerDialog(
      title: title,
      baselinePath: baselinePath,
      capturePath: capturePath,
      diffPath: diffPath,
      initialMode: start,
    ),
  );
}

class _DiffViewerDialog extends StatefulWidget {
  const _DiffViewerDialog({
    required this.title,
    required this.baselinePath,
    required this.capturePath,
    required this.diffPath,
    required this.initialMode,
  });

  final String title;
  final String? baselinePath;
  final String? capturePath;
  final String? diffPath;
  final DiffViewerMode initialMode;

  @override
  State<_DiffViewerDialog> createState() => _DiffViewerDialogState();
}

class _DiffViewerDialogState extends State<_DiffViewerDialog> {
  late DiffViewerMode _mode = widget.initialMode;
  double _slider = 0.5;

  bool get _hasBaseline =>
      widget.baselinePath != null && File(widget.baselinePath!).existsSync();
  bool get _hasCapture =>
      widget.capturePath != null && File(widget.capturePath!).existsSync();
  bool get _hasDiff =>
      widget.diffPath != null && File(widget.diffPath!).existsSync();
  bool get _canSlide => _hasBaseline && _hasCapture;

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    return Dialog(
      backgroundColor: c.surface0,
      insetPadding: const EdgeInsets.all(24),
      shape: RoundedRectangleBorder(
        borderRadius: const BorderRadius.all(FuzzSpace.cardRadius),
        side: BorderSide(color: c.border, width: 0.5),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.max,
        children: [
          _header(context),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
              child: _body(context),
            ),
          ),
        ],
      ),
    );
  }

  Widget _header(BuildContext context) {
    final c = context.fuzz;
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 8, 12),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: c.border, width: 0.5)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              widget.title,
              style: FuzzText.title.copyWith(color: c.textPrimary),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 12),
          SegmentedButton<DiffViewerMode>(
            segments: [
              const ButtonSegment(
                value: DiffViewerMode.sideBySide,
                label: Text('Side-by-side'),
                icon: Icon(Icons.view_column_outlined, size: 16),
              ),
              ButtonSegment(
                value: DiffViewerMode.slider,
                label: const Text('Slider'),
                icon: const Icon(Icons.compare_outlined, size: 16),
                enabled: _canSlide,
              ),
              ButtonSegment(
                value: DiffViewerMode.diffOnly,
                label: const Text('Diff'),
                icon: const Icon(Icons.gradient_outlined, size: 16),
                enabled: _hasDiff,
              ),
            ],
            selected: {_mode},
            showSelectedIcon: false,
            onSelectionChanged: (s) => setState(() => _mode = s.first),
          ),
          const SizedBox(width: 4),
          IconButton(
            tooltip: 'Close',
            icon: const Icon(Icons.close),
            onPressed: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }

  Widget _body(BuildContext context) {
    switch (_mode) {
      case DiffViewerMode.sideBySide:
        return _sideBySide(context);
      case DiffViewerMode.slider:
        return _sliderOverlay(context);
      case DiffViewerMode.diffOnly:
        return _diffOnly(context);
    }
  }

  Widget _sideBySide(BuildContext context) {
    final panels = <Widget>[
      _labeledPanel(context, 'Baseline', widget.baselinePath, _hasBaseline),
      _labeledPanel(context, 'Capture', widget.capturePath, _hasCapture),
      if (widget.diffPath != null)
        _labeledPanel(context, 'Diff', widget.diffPath, _hasDiff),
    ];
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var i = 0; i < panels.length; i++) ...[
          Expanded(child: panels[i]),
          if (i < panels.length - 1) const SizedBox(width: 12),
        ],
      ],
    );
  }

  Widget _diffOnly(BuildContext context) {
    return _labeledPanel(context, 'Diff', widget.diffPath, _hasDiff);
  }

  Widget _sliderOverlay(BuildContext context) {
    final c = context.fuzz;
    if (!_canSlide) {
      return _missingPanel(context, 'Slider needs baseline and capture');
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Drag the divider to compare baseline (left) and capture (right).',
            style: FuzzText.caption.copyWith(color: c.textMuted)),
        const SizedBox(height: 8),
        Expanded(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final w = constraints.maxWidth;
              final dividerX = (w * _slider).clamp(0.0, w);
              return Container(
                decoration: BoxDecoration(
                  color: c.surface1,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: c.border, width: 0.5),
                ),
                clipBehavior: Clip.antiAlias,
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onHorizontalDragUpdate: (d) {
                    setState(() {
                      _slider = (d.localPosition.dx / w).clamp(0.0, 1.0);
                    });
                  },
                  onTapDown: (d) {
                    setState(() {
                      _slider = (d.localPosition.dx / w).clamp(0.0, 1.0);
                    });
                  },
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      Image.file(
                        File(widget.capturePath!),
                        fit: BoxFit.contain,
                        alignment: Alignment.topCenter,
                      ),
                      ClipRect(
                        clipper: _LeftClipper(dividerX),
                        child: Image.file(
                          File(widget.baselinePath!),
                          fit: BoxFit.contain,
                          alignment: Alignment.topCenter,
                        ),
                      ),
                      Positioned(
                        left: dividerX - 1,
                        top: 0,
                        bottom: 0,
                        child: IgnorePointer(
                          child: Container(
                            width: 2,
                            color: c.accentFill,
                          ),
                        ),
                      ),
                      Positioned(
                        left: dividerX - 14,
                        top: 0,
                        bottom: 0,
                        child: Center(
                          child: IgnorePointer(
                            child: Container(
                              width: 28,
                              height: 28,
                              decoration: BoxDecoration(
                                color: c.accentFill,
                                shape: BoxShape.circle,
                                border:
                                    Border.all(color: c.onAccent, width: 2),
                              ),
                              child: Icon(Icons.swap_horiz,
                                  size: 16, color: c.onAccent),
                            ),
                          ),
                        ),
                      ),
                      Positioned(
                        left: 8,
                        top: 8,
                        child: _cornerTag(context, 'Baseline'),
                      ),
                      Positioned(
                        right: 8,
                        top: 8,
                        child: _cornerTag(context, 'Capture'),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _cornerTag(BuildContext context, String text) {
    final c = context.fuzz;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: c.surface2.withValues(alpha: 0.85),
        borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
        border: Border.all(color: c.border, width: 0.5),
      ),
      child: Text(text,
          style: FuzzText.caption
              .copyWith(color: c.textPrimary, fontWeight: FontWeight.w500)),
    );
  }

  Widget _labeledPanel(
      BuildContext context, String label, String? path, bool exists) {
    final c = context.fuzz;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: FuzzText.label.copyWith(color: c.textMuted)),
        const SizedBox(height: 4),
        Expanded(
          child: Container(
            decoration: BoxDecoration(
              color: c.surface1,
              borderRadius: BorderRadius.circular(6),
              border: Border.all(color: c.border, width: 0.5),
            ),
            clipBehavior: Clip.antiAlias,
            child: path == null
                ? Center(
                    child: Text('no baseline',
                        style: FuzzText.caption.copyWith(color: c.textMuted)))
                : !exists
                    ? Center(
                        child: Text('file missing',
                            style:
                                FuzzText.caption.copyWith(color: c.dangerText)))
                    : InteractiveViewer(
                        maxScale: 6,
                        child: Image.file(
                          File(path),
                          fit: BoxFit.contain,
                          alignment: Alignment.topCenter,
                        ),
                      ),
          ),
        ),
        if (path != null) ...[
          const SizedBox(height: 4),
          Text(path,
              style: FuzzText.mono
                  .copyWith(color: c.textMuted, fontSize: 11),
              maxLines: 1,
              overflow: TextOverflow.ellipsis),
        ],
      ],
    );
  }

  Widget _missingPanel(BuildContext context, String message) {
    final c = context.fuzz;
    return Container(
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: c.surface1,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: c.border, width: 0.5),
      ),
      child: Text(message,
          style: FuzzText.body.copyWith(color: c.textMuted)),
    );
  }
}

class _LeftClipper extends CustomClipper<Rect> {
  _LeftClipper(this.x);
  final double x;

  @override
  Rect getClip(Size size) => Rect.fromLTWH(0, 0, x, size.height);

  @override
  bool shouldReclip(covariant _LeftClipper old) => old.x != x;
}
