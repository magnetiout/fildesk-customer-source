import 'package:flutter/material.dart';

/// Remote CM presentation only: authorization is not video readiness.
/// No transport, FFI, permission or fabricated renderer-state transitions.
class FilCmAuthorizationStatus extends StatelessWidget {
  final bool authorized;
  final bool disconnected;
  final String elapsed;
  final String Function(String) translate;

  const FilCmAuthorizationStatus({super.key, required this.authorized,
    required this.disconnected, required this.elapsed, required this.translate});

  @override
  Widget build(BuildContext context) => Column(
    key: const ValueKey('fil-cm-authorization-status'),
    crossAxisAlignment: CrossAxisAlignment.start,
    mainAxisSize: MainAxisSize.min,
    children: [
      Text(translate(disconnected ? 'Disconnected' : authorized
          ? 'Access authorized' : 'Awaiting access approval'),
        style: const TextStyle(color: Colors.white)),
      if (authorized) ...[
        const SizedBox(height: 4),
        Text('${translate('Time in this window after access approval')}: $elapsed',
          style: const TextStyle(color: Colors.white70, fontSize: 12)),
      ],
      if (authorized && !disconnected) ...[
        const SizedBox(height: 4),
        Text(translate('Image status is shown in the operator window.'),
          style: const TextStyle(color: Colors.white70, fontSize: 12)),
      ],
    ],
  );
}

/// Only the default remote CM uses this finite-height layout. Existing action
/// widgets/callbacks are supplied unchanged; they remain outside the scroller.
class FilCmRemoteCardLayout extends StatelessWidget {
  final Widget header;
  final Widget permissions;
  final Widget controls;
  const FilCmRemoteCardLayout({super.key, required this.header,
    required this.permissions, required this.controls});
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Expanded(child: SingleChildScrollView(
        key: const ValueKey('fil-cm-authorization-scroll'),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [header, permissions]),
      )),
      controls,
    ],
  );
}
