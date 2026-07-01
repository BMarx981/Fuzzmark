import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:fuzzmark_app/screens/projects_screen.dart';
import 'package:fuzzmark_app/state/providers.dart';
import 'package:fuzzmark_app/state/recents.dart';
import 'package:fuzzmark_app/theme.dart';

void main() {
  testWidgets('Projects screen renders empty-state copy', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final recents = await RecentProjects.load();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [recentsProvider.overrideWithValue(recents)],
        child: MaterialApp(
          theme: buildLightTheme(),
          home: ProjectsScreen(onOpen: (_) {}),
        ),
      ),
    );

    expect(find.text('Projects'), findsOneWidget);
    expect(find.text('New project'), findsAtLeastNWidgets(1));
    expect(find.text('Open project file'), findsOneWidget);
    expect(find.textContaining('No recent projects'), findsOneWidget);
  });
}
