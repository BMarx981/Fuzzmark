import 'package:flutter/material.dart';

const _accent = Color(0xFF4A7CFF);
const _monoFamily = 'monospace';

ThemeData buildLightTheme() => _buildTheme(Brightness.light);

ThemeData buildDarkTheme() => _buildTheme(Brightness.dark);

ThemeData _buildTheme(Brightness brightness) {
  final scheme = ColorScheme.fromSeed(
    seedColor: _accent,
    brightness: brightness,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    visualDensity: VisualDensity.adaptivePlatformDensity,
    textTheme: Typography.material2021(platform: TargetPlatform.macOS)
        .black
        .apply(
          bodyColor: scheme.onSurface,
          displayColor: scheme.onSurface,
        ),
    extensions: const [FuzzmarkColors(mono: _monoFamily)],
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
