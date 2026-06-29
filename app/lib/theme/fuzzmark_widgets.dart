import 'package:flutter/material.dart';
import 'fuzzmark_tokens.dart';

enum RunStatus { running, passed, diffs, failed }

extension RunStatusLabel on RunStatus {
  String get label => switch (this) {
        RunStatus.running => 'Running',
        RunStatus.passed => 'Passed',
        RunStatus.diffs => 'Diffs',
        RunStatus.failed => 'Failed',
      };
  IconData get icon => switch (this) {
        RunStatus.running => Icons.sync,
        RunStatus.passed => Icons.check,
        RunStatus.diffs => Icons.visibility_outlined,
        RunStatus.failed => Icons.error_outline,
      };
}

enum Severity { high, medium, low }

extension SeverityLabel on Severity {
  String get label => switch (this) {
        Severity.high => 'High',
        Severity.medium => 'Medium',
        Severity.low => 'Low',
      };
}

class StatusBadge extends StatelessWidget {
  final RunStatus status;
  const StatusBadge(this.status, {super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    final (Color bg, Color fg) = switch (status) {
      RunStatus.running => (c.accentBg, c.accentText),
      RunStatus.passed => (c.successBg, c.successText),
      RunStatus.diffs => (c.warningBg, c.warningText),
      RunStatus.failed => (c.dangerBg, c.dangerText),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(status.icon, size: 13, color: fg),
          const SizedBox(width: 5),
          Text(status.label, style: FuzzText.caption.copyWith(color: fg, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}

class SeverityBadge extends StatelessWidget {
  final Severity severity;
  const SeverityBadge(this.severity, {super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    final (Color bg, Color fg, bool bordered) = switch (severity) {
      Severity.high => (c.dangerBg, c.dangerText, false),
      Severity.medium => (c.warningBg, c.warningText, false),
      Severity.low => (c.surface2, c.textSecondary, true),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 2),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
        border: bordered ? Border.all(color: c.border, width: 0.5) : null,
      ),
      child: Text(severity.label, style: FuzzText.caption.copyWith(color: fg, fontWeight: FontWeight.w500)),
    );
  }
}

class MetricCard extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;
  const MetricCard({super.key, required this.label, required this.value, this.valueColor});

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: c.surface1,
        borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: FuzzText.caption.copyWith(color: c.textMuted)),
          const SizedBox(height: 4),
          Text(value, style: FuzzText.metric.copyWith(color: valueColor ?? c.textPrimary)),
        ],
      ),
    );
  }
}

class FuzzCell {
  final int flex;
  final Widget child;
  const FuzzCell(this.child, {this.flex = 1});
}

class FuzzTableRow extends StatelessWidget {
  final List<FuzzCell> cells;
  final bool header;
  const FuzzTableRow({super.key, required this.cells, this.header = false});

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    final style = header
        ? FuzzText.caption.copyWith(color: c.textMuted, fontWeight: FontWeight.w500)
        : FuzzText.body.copyWith(color: c.textPrimary);
    return Container(
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: c.border, width: 0.5)),
      ),
      padding: const EdgeInsets.symmetric(vertical: 11),
      child: DefaultTextStyle.merge(
        style: style,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            for (final cell in cells)
              Expanded(
                flex: cell.flex,
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  child: cell.child,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

enum FuzzStateKind { empty, loading, error }

class FuzzStateCard extends StatelessWidget {
  final FuzzStateKind kind;
  final String title;
  final String message;
  final String? actionLabel;
  final IconData? actionIcon;
  final VoidCallback? onAction;
  final double? progress;

  const FuzzStateCard({
    super.key,
    required this.kind,
    required this.title,
    required this.message,
    this.actionLabel,
    this.actionIcon,
    this.onAction,
    this.progress,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    final (IconData icon, Color iconBg, Color iconColor) = switch (kind) {
      FuzzStateKind.empty => (Icons.inbox_outlined, c.surface1, c.textMuted),
      FuzzStateKind.loading => (Icons.sync, c.accentBg, c.accentText),
      FuzzStateKind.error => (Icons.link_off, c.dangerBg, c.dangerText),
    };
    final filled = kind == FuzzStateKind.empty;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 22),
      constraints: const BoxConstraints(minHeight: 188),
      decoration: BoxDecoration(
        color: c.surface2,
        borderRadius: const BorderRadius.all(FuzzSpace.cardRadius),
        border: Border.all(color: c.border, width: 0.5),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: iconBg,
              borderRadius: BorderRadius.circular(11),
            ),
            child: Icon(icon, size: 22, color: iconColor),
          ),
          const SizedBox(height: 12),
          Text(title, style: FuzzText.heading.copyWith(color: c.textPrimary), textAlign: TextAlign.center),
          const SizedBox(height: 5),
          Text(message, style: FuzzText.caption.copyWith(color: c.textMuted), textAlign: TextAlign.center),
          if (progress != null) ...[
            const SizedBox(height: 14),
            FractionallySizedBox(
              widthFactor: 0.8,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(3),
                child: LinearProgressIndicator(
                  value: progress,
                  minHeight: 5,
                  backgroundColor: c.surface1,
                  valueColor: AlwaysStoppedAnimation(c.accentFill),
                ),
              ),
            ),
          ],
          if (onAction != null) ...[
            const SizedBox(height: 14),
            _StateAction(
              label: actionLabel ?? '',
              icon: actionIcon,
              filled: filled,
              onTap: onAction!,
            ),
          ],
        ],
      ),
    );
  }
}

class _StateAction extends StatelessWidget {
  final String label;
  final IconData? icon;
  final bool filled;
  final VoidCallback onTap;
  const _StateAction({required this.label, required this.icon, required this.filled, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final c = context.fuzz;
    return Material(
      color: filled ? c.accentFill : Colors.transparent,
      borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
      child: InkWell(
        onTap: onTap,
        borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
        child: Container(
          height: 32,
          padding: const EdgeInsets.symmetric(horizontal: 13),
          decoration: BoxDecoration(
            borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
            border: filled ? null : Border.all(color: c.borderStrong, width: 0.5),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: 15, color: filled ? c.onAccent : c.textPrimary),
                const SizedBox(width: 6),
              ],
              Text(
                label,
                style: FuzzText.label.copyWith(
                  color: filled ? c.onAccent : c.textPrimary,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
