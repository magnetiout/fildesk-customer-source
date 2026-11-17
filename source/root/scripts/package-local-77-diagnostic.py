"""Package a locally built 77 pair for private two-PC diagnosis only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def package(run: Path, source: Path, kit: Path, workspace: Path) -> dict:
    build = load(run / "evidence/RESULT.json")
    receipt = load(source / "SOURCE-RECEIPT.json")
    artifact_environment = build.get('artifactEnvironment', 'staging')
    if artifact_environment not in ('staging', 'production-candidate'):
        raise ValueError('Unknown private candidate output')
    if build["status"] != "LOCAL_DIAGNOSTIC_PAIR_BUILT_PHYSICAL_NOT_RUN":
        raise ValueError("Both local role builds must pass before packaging")
    if build["sourceSHA256"] != receipt["clientSnapshotSHA256"]:
        raise ValueError("Build/source identity mismatch")
    dest = run / "private-diagnostic-delivery"
    if dest.exists():
        raise FileExistsError(dest)
    roles: dict[str, dict] = {}
    for role in ("customer", "operator"):
        item = build["roleChecks"].get(role)
        exe = run / role / "artifacts/windows" / artifact_environment / role / "FilDesk.exe"
        if not item or item["status"] != "LOCAL_BUILD_PASS_PHYSICAL_NOT_RUN":
            raise ValueError(f"Unverified {role} build")
        if not exe.is_file() or sha(exe) != item["exeSHA256"]:
            raise ValueError(f"Changed {role} executable")
        roles[role] = {"exe": exe, "sha256": item["exeSHA256"], "bytes": exe.stat().st_size}
    if roles["customer"]["sha256"] == roles["operator"]["sha256"]:
        raise ValueError("Role executables must differ")
    dest.mkdir()
    manifest = {
        "schema": 1,
        "version": "1.5.0+77",
        "purpose": "PRIVATE_TWO_PC_DIAGNOSTIC_ONLY",
        "sourceSnapshotSHA256": receipt["clientSnapshotSHA256"],
        "physicalAcceptance": "NOT_RUN",
        "publicRelease": "BLOCKED",
        "environment": artifact_environment,
        "roles": {},
    }
    for role, item in roles.items():
        label = 'Publication-Candidate' if artifact_environment == 'production-candidate' else 'Diagnostic'
        name = f"FilDesk-1.5.0-77-{role.title()}-{label}-20261116.zip"
        archive = dest / name
        release = run / role / "client/flutter/build/windows/x64/runner/Release"
        artifacts = item["exe"].parent
        files = {
            "FilDesk.exe": item["exe"],
            "LICENSES/LICENSE-RustDesk.txt": release / "LICENSE-RustDesk.txt",
            "LICENSES/SOURCE-NOTICE.md": release / "SOURCE-NOTICE.md",
        }
        for optional in ("payload-catalog.json", "PE-DEPENDENCIES.json", "manifest.json", "SHA256SUMS"):
            candidate = artifacts / optional
            if candidate.is_file():
                files[optional] = candidate
        for notice in ("UNI-LINKS-LICENSE.txt", "FLUTTER-NOTICES-complete.txt"):
            candidate = kit / notice
            if candidate.is_file():
                files["LICENSES/" + notice] = candidate
        readme = (
            f"FilDesk 1.5.0+77 {role.title()} — PRIVATE DIAGNOSTIC ONLY\n"
            f"Executable SHA-256: {item['sha256']}\n"
            "Extract the complete ZIP into its own folder. Keep prior installations and profiles.\n"
            "A new two-PC video/input/UAC test is required. Do not treat build PASS as physical acceptance.\n"
            "The separate corresponding-source base and matching diagnostic supplement accompany this pair.\n"
            "Operator stays private. No public release or production change is approved.\n"
        )
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for path, actual in files.items():
                if not actual.is_file():
                    raise FileNotFoundError(actual)
                z.write(actual, path)
            z.writestr("READ-ME-FIRST.txt", readme)
            z.writestr("SOURCE-RECEIPT.json", json.dumps(receipt, indent=2) + "\n")
            with zipfile.ZipFile(kit / "compliance.zip") as notices:
                if notices.testzip() is not None:
                    raise ValueError("Prior complete notices CRC failed")
                for member in notices.infolist():
                    parts = Path(member.filename.replace("\\", "/")).parts
                    if member.is_dir():
                        continue
                    if member.filename in ("SOURCE-AVAILABILITY.txt", "MODIFICATIONS.md"):
                        # The retained 76 notices describe an older source delta.
                        continue
                    if not parts or any(part in ("", ".", "..") or ":" in part for part in parts):
                        raise ValueError("Unsafe notice path")
                    if member.file_size > 16 * 1024 * 1024:
                        raise ValueError("Unexpectedly large notice")
                    z.writestr("LICENSES/COMPLIANCE/" + "/".join(parts), notices.read(member))
            z.writestr(
                "LICENSES/SOURCE-AVAILABILITY-77-DIAGNOSTIC.txt",
                "This private 1.5.0+77 diagnostic candidate is accompanied by "
                "FilDesk76-Corresponding-Source-Base.zip and "
                "FilDesk77-Diagnostic-Source-and-Build-Supplement.zip. "
                "The supplement contains the exact local root/client snapshots "
                "and their SHA-256 receipt. The prior dependency notices are reused "
                "because Cargo.lock and the Flutter dependency graph are unchanged. "
                "Physical acceptance and public release are pending.\n",
            )
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None or z.namelist().count("FilDesk.exe") != 1:
                raise ValueError(f"Invalid {role} ZIP")
        manifest["roles"][role] = {
            "filename": name,
            "zipSHA256": sha(archive),
            "exeSHA256": item["sha256"],
            "bytes": archive.stat().st_size,
        }

    base = kit / "corresponding-source.zip"
    base_copy = dest / "FilDesk76-Corresponding-Source-Base.zip"
    shutil.copyfile(base, base_copy)
    if sha(base_copy) != sha(base):
        raise ValueError("Corresponding-source base copy differs")
    manifest["sourceBase"] = {"filename": base_copy.name, "sha256": sha(base_copy)}
    supplement = dest / "FilDesk77-Diagnostic-Source-and-Build-Supplement.zip"
    with zipfile.ZipFile(supplement, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name in ("root-snapshot.zip", "client-snapshot.zip", "SOURCE-RECEIPT.json"):
            z.write(source / name, name)
        for name in ("prepare-local-77-diagnostic.py", "prepare-publication-candidate.py", "build-local-77-diagnostic.ps1", "package-local-77-diagnostic.py"):
            z.write(workspace / "scripts" / name, "build/" + name)
    with zipfile.ZipFile(supplement) as z:
        if z.testzip() is not None:
            raise ValueError("Diagnostic supplement CRC failed")
    manifest["sourceSupplement"] = {"filename": supplement.name, "sha256": sha(supplement)}
    (dest / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    lines = [f"{value['zipSHA256']}  {value['filename']}" for value in manifest["roles"].values()]
    lines += [f"{manifest[key]['sha256']}  {manifest[key]['filename']}" for key in ("sourceBase", "sourceSupplement")]
    (dest / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    result = package(args.run.resolve(strict=True), args.source.resolve(strict=True),
                     args.kit.resolve(strict=True), args.workspace.resolve(strict=True))
    print(json.dumps(result, indent=2))
