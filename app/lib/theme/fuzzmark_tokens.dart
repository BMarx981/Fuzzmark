import 'package:flutter/material.dart';

@immutable
class FuzzColors extends ThemeExtension<FuzzColors> {
  final Color surface0;
  final Color surface1;
  final Color surface2;
  final Color border;
  final Color borderStrong;
  final Color textPrimary;
  final Color textSecondary;
  final Color textMuted;
  final Color accentBg;
  final Color accentText;
  final Color accentFill;
  final Color onAccent;
  final Color successBg;
  final Color successText;
  final Color warningBg;
  final Color warningText;
  final Color dangerBg;
  final Color dangerText;
  final Color dangerFill;
  final Color onDanger;
  final Color diff;

  const FuzzColors({
    required this.surface0,
    required this.surface1,
    required this.surface2,
    required this.border,
    required this.borderStrong,
    required this.textPrimary,
    required this.textSecondary,
    required this.textMuted,
    required this.accentBg,
    required this.accentText,
    required this.accentFill,
    required this.onAccent,
    required this.successBg,
    required this.successText,
    required this.warningBg,
    required this.warningText,
    required this.dangerBg,
    required this.dangerText,
    required this.dangerFill,
    required this.onDanger,
    required this.diff,
  });

  static const light = FuzzColors(
    surface0: Color(0xFFF0EDE6),
    surface1: Color(0xFFF7F5F0),
    surface2: Color(0xFFFFFFFF),
    border: Color(0xFFE6E3DB),
    borderStrong: Color(0xFFD3D1C7),
    textPrimary: Color(0xFF2C2C2A),
    textSecondary: Color(0xFF5F5E5A),
    textMuted: Color(0xFF888780),
    accentBg: Color(0xFFE6F1FB),
    accentText: Color(0xFF185FA5),
    accentFill: Color(0xFF378ADD),
    onAccent: Color(0xFFFFFFFF),
    successBg: Color(0xFFEAF3DE),
    successText: Color(0xFF3B6D11),
    warningBg: Color(0xFFFAEEDA),
    warningText: Color(0xFF854F0B),
    dangerBg: Color(0xFFFCEBEB),
    dangerText: Color(0xFFA32D2D),
    dangerFill: Color(0xFFE24B4A),
    onDanger: Color(0xFFFFFFFF),
    diff: Color(0xFFD4537E),
  );

  static const dark = FuzzColors(
    surface0: Color(0xFF1A1A18),
    surface1: Color(0xFF262624),
    surface2: Color(0xFF2F2F2C),
    border: Color(0xFF3A3A36),
    borderStrong: Color(0xFF4B4B46),
    textPrimary: Color(0xFFECEAE3),
    textSecondary: Color(0xFFB4B2A9),
    textMuted: Color(0xFF87867F),
    accentBg: Color(0xFF0C447C),
    accentText: Color(0xFF85B7EB),
    accentFill: Color(0xFF378ADD),
    onAccent: Color(0xFFFFFFFF),
    successBg: Color(0xFF27500A),
    successText: Color(0xFFC0DD97),
    warningBg: Color(0xFF633806),
    warningText: Color(0xFFFAC775),
    dangerBg: Color(0xFF791F1F),
    dangerText: Color(0xFFF7C1C1),
    dangerFill: Color(0xFFE24B4A),
    onDanger: Color(0xFFFFFFFF),
    diff: Color(0xFFD4537E),
  );

  @override
  FuzzColors copyWith({
    Color? surface0,
    Color? surface1,
    Color? surface2,
    Color? border,
    Color? borderStrong,
    Color? textPrimary,
    Color? textSecondary,
    Color? textMuted,
    Color? accentBg,
    Color? accentText,
    Color? accentFill,
    Color? onAccent,
    Color? successBg,
    Color? successText,
    Color? warningBg,
    Color? warningText,
    Color? dangerBg,
    Color? dangerText,
    Color? dangerFill,
    Color? onDanger,
    Color? diff,
  }) {
    return FuzzColors(
      surface0: surface0 ?? this.surface0,
      surface1: surface1 ?? this.surface1,
      surface2: surface2 ?? this.surface2,
      border: border ?? this.border,
      borderStrong: borderStrong ?? this.borderStrong,
      textPrimary: textPrimary ?? this.textPrimary,
      textSecondary: textSecondary ?? this.textSecondary,
      textMuted: textMuted ?? this.textMuted,
      accentBg: accentBg ?? this.accentBg,
      accentText: accentText ?? this.accentText,
      accentFill: accentFill ?? this.accentFill,
      onAccent: onAccent ?? this.onAccent,
      successBg: successBg ?? this.successBg,
      successText: successText ?? this.successText,
      warningBg: warningBg ?? this.warningBg,
      warningText: warningText ?? this.warningText,
      dangerBg: dangerBg ?? this.dangerBg,
      dangerText: dangerText ?? this.dangerText,
      dangerFill: dangerFill ?? this.dangerFill,
      onDanger: onDanger ?? this.onDanger,
      diff: diff ?? this.diff,
    );
  }

  @override
  FuzzColors lerp(ThemeExtension<FuzzColors>? other, double t) {
    if (other is! FuzzColors) return this;
    return FuzzColors(
      surface0: Color.lerp(surface0, other.surface0, t)!,
      surface1: Color.lerp(surface1, other.surface1, t)!,
      surface2: Color.lerp(surface2, other.surface2, t)!,
      border: Color.lerp(border, other.border, t)!,
      borderStrong: Color.lerp(borderStrong, other.borderStrong, t)!,
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t)!,
      textMuted: Color.lerp(textMuted, other.textMuted, t)!,
      accentBg: Color.lerp(accentBg, other.accentBg, t)!,
      accentText: Color.lerp(accentText, other.accentText, t)!,
      accentFill: Color.lerp(accentFill, other.accentFill, t)!,
      onAccent: Color.lerp(onAccent, other.onAccent, t)!,
      successBg: Color.lerp(successBg, other.successBg, t)!,
      successText: Color.lerp(successText, other.successText, t)!,
      warningBg: Color.lerp(warningBg, other.warningBg, t)!,
      warningText: Color.lerp(warningText, other.warningText, t)!,
      dangerBg: Color.lerp(dangerBg, other.dangerBg, t)!,
      dangerText: Color.lerp(dangerText, other.dangerText, t)!,
      dangerFill: Color.lerp(dangerFill, other.dangerFill, t)!,
      onDanger: Color.lerp(onDanger, other.onDanger, t)!,
      diff: Color.lerp(diff, other.diff, t)!,
    );
  }
}

class FuzzSpace {
  const FuzzSpace._();
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double radius = 8;
  static const double radiusCard = 12;
  static const Radius cardRadius = Radius.circular(radiusCard);
  static const Radius controlRadius = Radius.circular(radius);
}

class FuzzText {
  const FuzzText._();
  static const TextStyle title =
      TextStyle(fontSize: 16, fontWeight: FontWeight.w500, height: 1.3);
  static const TextStyle heading =
      TextStyle(fontSize: 14, fontWeight: FontWeight.w500, height: 1.4);
  static const TextStyle body =
      TextStyle(fontSize: 13, fontWeight: FontWeight.w400, height: 1.5);
  static const TextStyle label =
      TextStyle(fontSize: 12.5, fontWeight: FontWeight.w400, height: 1.4);
  static const TextStyle caption =
      TextStyle(fontSize: 11.5, fontWeight: FontWeight.w400, height: 1.4);
  static const TextStyle metric =
      TextStyle(fontSize: 22, fontWeight: FontWeight.w500, height: 1.1);
  static const TextStyle mono = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.w400,
    height: 1.4,
    fontFamilyFallback: ['monospace'],
  );
}

extension FuzzTheme on BuildContext {
  FuzzColors get fuzz => Theme.of(this).extension<FuzzColors>()!;
}

ThemeData fuzzTheme(Brightness brightness) {
  final colors = brightness == Brightness.dark ? FuzzColors.dark : FuzzColors.light;
  return ThemeData(
    brightness: brightness,
    scaffoldBackgroundColor: colors.surface0,
    extensions: [colors],
  );
}
