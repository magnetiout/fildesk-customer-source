# Client CI toolchain contract

The three workflows bridge.yml, playground.yml and flutter-build.yml use Rust
1.90.0 for their four main RUST_VERSION/MAC_RUST_VERSION pins. Cargo.toml requires
Rust 1.88 or newer. The locally validated compiler is rustc 1.90.0
(1159e78c4 2025-09-14). Action revisions and build steps are unchanged.

This pin correction is not a CI or cross-platform runtime acceptance result.
The original SCITER_RUST_VERSION 1.75 and explicit Windows i686 Sciter
nightly-2023-10-13 override are intentionally unchanged. Both legacy Sciter paths
remain BLOCKED: their compilers predate the declared minimum Rust 1.88, while
the preserved source comment identifies Sciter ABI incompatibility from Rust
1.78. Their abi_thiscall/i128 ABI assumptions need a separate toolchain/ABI
migration and native tests. Rust 1.90.0 is the locally tested main compiler,
not the declared MSRV. Windows/macOS, signing and release acceptance remain
unverified here. F-Droid reads these workflow variables; its runtime also needs
independent validation.

## Generated bridge inputs

bridge.yml pins cargo-expand 1.0.95 and flutter_rust_bridge_codegen 1.80.1.
It installs both with --locked, runs Flutter dependency resolution (and the
existing matrix-specific source patches), then invokes:

```sh
~/.cargo/bin/flutter_rust_bridge_codegen --rust-input ./src/flutter_ffi.rs --dart-output ./flutter/lib/generated_bridge.dart --c-output ./flutter/macos/Runner/bridge_generated.h
```

The workflow copies that header to flutter/ios/Runner/bridge_generated.h and
uploads the existing generated Rust/Dart/header outputs. This task did not run
that generator or claim reproducible generation. Local compiler evidence uses
preexisting, ignored, owned-copy inputs, never a historical secret checkout:

| Input | SHA256 |
|---|---|
| src/bridge_generated.rs | 353fce2acb0eaccefa2efe36440dc5ae36f9b08ff1021d0ff2a4f8b89f071862 |
| src/bridge_generated.io.rs | 8012ad417c891e497c99b57863d6006139da9217def5c6bf07f4cb8295fa8120 |

A clean CI runner must actually generate these inputs. Existing local Clippy
success with copied inputs proves neither the generator nor a clean CI run.
