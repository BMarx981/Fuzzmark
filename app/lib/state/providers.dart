import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/client.dart';
import '../engine/engine_process.dart';
import 'recents.dart';

final apiProvider = Provider<FuzzmarkApi>((ref) {
  final api = FuzzmarkApi();
  ref.onDispose(api.close);
  return api;
});

final engineProvider = Provider<EngineProcess>((ref) {
  final engine = EngineProcess();
  ref.onDispose(engine.stop);
  return engine;
});

final engineBootProvider = FutureProvider<void>((ref) async {
  await ref.read(engineProvider).start();
});

/// Resolved on app boot in `main` and injected via `ProviderScope` overrides;
/// reading without an override is a programming error.
final recentsProvider = Provider<RecentProjects>((ref) {
  throw UnimplementedError(
    'recentsProvider must be overridden by ProviderScope before use',
  );
});
