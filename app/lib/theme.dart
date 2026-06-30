import 'package:flutter/material.dart';

import 'theme/fuzzmark_tokens.dart';

const _accent = Color(0xFF4A7CFF);
const _monoFamily = 'monospace';

ThemeData buildLightTheme() => _buildTheme(Brightness.light);

ThemeData buildDarkTheme() => _buildTheme(Brightness.dark);

ThemeData _buildTheme(Brightness brightness) {
  final scheme = ColorScheme.fromSeed(
    seedColor: _accent,
    brightness: brightness,
  );
  final fuzz =
      brightness == Brightness.dark ? FuzzColors.dark : FuzzColors.light;

  const controlShape = RoundedRectangleBorder(
    borderRadius: BorderRadius.all(FuzzSpace.controlRadius),
  );
  final inputBorder = OutlineInputBorder(
    borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
    borderSide: BorderSide(color: fuzz.border, width: 0.5),
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: fuzz.surface0,
    canvasColor: fuzz.surface0,
    dividerColor: fuzz.border,
    visualDensity: VisualDensity.adaptivePlatformDensity,
    textTheme: Typography.material2021(platform: TargetPlatform.macOS)
        .black
        .apply(
          bodyColor: fuzz.textPrimary,
          displayColor: fuzz.textPrimary,
        ),
    iconTheme: IconThemeData(color: fuzz.textSecondary, size: 18),
    dividerTheme: DividerThemeData(
      color: fuzz.border,
      thickness: 0.5,
      space: 0.5,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: fuzz.accentFill,
        foregroundColor: fuzz.onAccent,
        disabledBackgroundColor: fuzz.surface1,
        disabledForegroundColor: fuzz.textMuted,
        textStyle: FuzzText.label.copyWith(fontWeight: FontWeight.w500),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        shape: controlShape,
        elevation: 0,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: fuzz.textPrimary,
        side: BorderSide(color: fuzz.borderStrong, width: 0.5),
        textStyle: FuzzText.label.copyWith(fontWeight: FontWeight.w500),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        shape: controlShape,
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: fuzz.accentText,
        disabledForegroundColor: fuzz.textMuted,
        textStyle: FuzzText.label.copyWith(fontWeight: FontWeight.w500),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        shape: controlShape,
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: fuzz.surface2,
      isDense: true,
      contentPadding:
          const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      hintStyle: FuzzText.body.copyWith(color: fuzz.textMuted),
      labelStyle: FuzzText.label.copyWith(color: fuzz.textSecondary),
      floatingLabelStyle: FuzzText.label.copyWith(color: fuzz.accentText),
      helperStyle: FuzzText.caption.copyWith(color: fuzz.textMuted),
      errorStyle: FuzzText.caption.copyWith(color: fuzz.dangerText),
      border: inputBorder,
      enabledBorder: inputBorder,
      disabledBorder: inputBorder,
      focusedBorder: OutlineInputBorder(
        borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
        borderSide: BorderSide(color: fuzz.accentFill, width: 1),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
        borderSide: BorderSide(color: fuzz.dangerFill, width: 0.5),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
        borderSide: BorderSide(color: fuzz.dangerFill, width: 1),
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: fuzz.surface2,
      surfaceTintColor: Colors.transparent,
      titleTextStyle: FuzzText.title.copyWith(color: fuzz.textPrimary),
      contentTextStyle: FuzzText.body.copyWith(color: fuzz.textPrimary),
      shape: RoundedRectangleBorder(
        borderRadius: const BorderRadius.all(FuzzSpace.cardRadius),
        side: BorderSide(color: fuzz.border, width: 0.5),
      ),
      elevation: 0,
    ),
    chipTheme: ChipThemeData(
      backgroundColor: fuzz.surface1,
      selectedColor: fuzz.accentBg,
      disabledColor: fuzz.surface1,
      labelStyle: FuzzText.caption.copyWith(color: fuzz.textSecondary),
      secondaryLabelStyle: FuzzText.caption.copyWith(color: fuzz.accentText),
      side: BorderSide(color: fuzz.border, width: 0.5),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.all(FuzzSpace.controlRadius),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      checkmarkColor: fuzz.accentText,
      showCheckmark: true,
      brightness: brightness,
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.disabled)) return fuzz.textMuted;
        if (states.contains(WidgetState.selected)) return fuzz.onAccent;
        return fuzz.surface2;
      }),
      trackColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.disabled)) return fuzz.surface1;
        if (states.contains(WidgetState.selected)) return fuzz.accentFill;
        return fuzz.borderStrong;
      }),
      trackOutlineColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return Colors.transparent;
        return fuzz.borderStrong;
      }),
    ),
    checkboxTheme: CheckboxThemeData(
      fillColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.disabled)) return fuzz.surface1;
        if (states.contains(WidgetState.selected)) return fuzz.accentFill;
        return fuzz.surface2;
      }),
      checkColor: WidgetStateProperty.all(fuzz.onAccent),
      side: BorderSide(color: fuzz.borderStrong, width: 1),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(3),
      ),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: fuzz.accentFill,
      linearTrackColor: fuzz.surface1,
      circularTrackColor: fuzz.surface1,
      linearMinHeight: 4,
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: fuzz.textPrimary,
      contentTextStyle: FuzzText.body.copyWith(color: fuzz.surface0),
      actionTextColor: fuzz.accentText,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.all(FuzzSpace.controlRadius),
      ),
      behavior: SnackBarBehavior.floating,
      elevation: 0,
    ),
    listTileTheme: ListTileThemeData(
      titleTextStyle: FuzzText.body.copyWith(color: fuzz.textPrimary),
      subtitleTextStyle: FuzzText.caption.copyWith(color: fuzz.textMuted),
      iconColor: fuzz.textSecondary,
      selectedTileColor: fuzz.accentBg,
      selectedColor: fuzz.accentText,
    ),
    tooltipTheme: TooltipThemeData(
      decoration: BoxDecoration(
        color: fuzz.textPrimary,
        borderRadius: const BorderRadius.all(FuzzSpace.controlRadius),
      ),
      textStyle: FuzzText.caption.copyWith(color: fuzz.surface0),
      waitDuration: const Duration(milliseconds: 400),
    ),
    extensions: [const FuzzmarkColors(mono: _monoFamily), fuzz],
  );
}

@immutable
class FuzzmarkColors extends ThemeExtension<FuzzmarkColors> {
  const FuzzmarkColors({required this.mono});

  final String mono;

  @override
  FuzzmarkColors copyWith({String? mono}) =>
      FuzzmarkColors(mono: mono ?? this.mono);

  @override
  FuzzmarkColors lerp(ThemeExtension<FuzzmarkColors>? other, double t) {
    if (other is! FuzzmarkColors) return this;
    return FuzzmarkColors(mono: t < 0.5 ? mono : other.mono);
  }
}
