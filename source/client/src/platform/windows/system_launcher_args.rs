// SPDX-License-Identifier: AGPL-3.0-only
use std::io;

pub(super) fn permitted(profile: &str, arguments: &str) -> bool {
    profile == "customer" && arguments.split_ascii_whitespace().any(|s| s.starts_with("--portable-service-shmem-name="))
}

pub(super) fn command(executable: &[u16], arguments: &str) -> io::Result<Vec<u16>> {
    let invalid = || {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "Invalid portable SYSTEM helper arguments",
        )
    };
    if executable.is_empty() || executable.contains(&0) || executable.contains(&(b'"' as u16)) {
        return Err(invalid());
    }
    let (mut helper, mut noinstall, mut shared_memory) = (false, false, false);
    for argument in arguments.split_ascii_whitespace() {
        if argument == "--run-as-system" && !helper {
            helper = true;
        } else if argument == "--noinstall" && !noinstall {
            noinstall = true;
        } else if let Some(name) = argument.strip_prefix("--portable-service-shmem-name=") {
            if shared_memory
                || name.is_empty()
                || name.len() > 64
                || !name
                    .bytes()
                    .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
            {
                return Err(invalid());
            }
            shared_memory = true;
        } else {
            return Err(invalid());
        }
    }
    if !helper {
        return Err(invalid());
    }
    let mut command = vec![b'"' as u16];
    command.extend_from_slice(executable);
    command.extend([b'"' as u16, b' ' as u16]);
    command.extend(arguments.encode_utf16());
    command.push(0);
    // CreateProcessWithTokenW documents a 1024-character command-line limit.
    if command.len() > 1024 {
        return Err(invalid());
    }
    Ok(command)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn customer_scoped_helper_replaces_the_erroneous_customer_denial() {
        let scoped="--run-as-system --portable-service-shmem-name=FilDesk_123";
        assert!(permitted("customer",scoped));
        assert!(command(&[65],scoped).is_ok());
        assert!(!permitted("operator",scoped));
        assert!(!permitted("fallback",scoped));
        assert!(!permitted("customer","--run-as-system"));
        assert!(command(&[65],"--run-as-system --portable-service-shmem-name=../escape").is_err());
    }

    #[test]
    fn unicode_space_and_long_paths_keep_exact_helper_and_ipc_arguments() {
        let exe = format!("C:\\Destek araçları\\{}\\FilDesk.exe", "a".repeat(280));
        let args = "--noinstall --run-as-system --portable-service-shmem-name=FilDesk_abc-123";
        let built = command(&exe.encode_utf16().collect::<Vec<_>>(), args).unwrap();
        assert_eq!(
            String::from_utf16(&built[..built.len() - 1]).unwrap(),
            format!("\"{exe}\" {args}")
        );
        assert_eq!(built.last(), Some(&0));
    }

    #[test]
    fn command_or_profile_switches_and_invalid_ipc_names_are_rejected() {
        let exe = "C:\\FilDesk.exe".encode_utf16().collect::<Vec<_>>();
        for args in [
            "",
            "--install",
            "--run-as-system --run-as-system",
            "--run-as-system --connect 123",
            "--run-as-system --portable-service-shmem-name=../bad",
            "--run-as-system --portable-service-shmem-name=",
        ] {
            assert!(command(&exe, args).is_err(), "{args}");
        }
        assert!(command(&[0], "--run-as-system").is_err());
        assert!(command(&[65; 1024], "--run-as-system").is_err());
    }
}
