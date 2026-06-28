import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:fuzzmark_app/screens/projects_screen.dart';
import 'package:fuzzmark_app/api/client.dart';
import 'package:fuzzmark_app/state/recents.dart';

void main() {
  testWidgets('Projects screen renders empty-state copy', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final recents = await RecentProjects.load();

    await tester.pumpWidget(MaterialApp(
      home: ProjectsScreen(
        api: FuzzmarkApi(),
        recents: recents,
        onOpen: (_) {},
      ),
    ));

    expect(find.text('Projects'), findsOneWidget);
    expect(find.text('New project'), findsOneWidget);
    expect(find.text('Open project file'), findsOneWidget);
    expect(find.textContaining('No recent projects yet'), findsOneWidget);
  });
}
