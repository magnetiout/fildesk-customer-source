//! POSIX shell encoding for literal argv, never implicit trusted-script parsing.
//! No shell, sudo, identity, filesystem or network side effects are performed here.
pub fn quote(arg: &str) -> Result<String, &'static str> {
    if arg.contains('\0') {
        return Err("NUL is not representable in a process argument");
    }
    Ok(format!("'{}'", arg.replace('\'', "'\\''")))
}

pub fn join(args: &[String]) -> Result<String, &'static str> {
    if args.is_empty() || args[0].is_empty() {
        return Err("An executable argument is required");
    }
    args.iter()
        .map(|arg| quote(arg))
        .collect::<Result<Vec<_>, _>>()
        .map(|args| args.join(" "))
}

/// Only a portable literal stem is accepted; the service suffix is controlled here.
/// This prevents application-level glob/path expansion, not reserved-name collisions.
pub fn service_unit(stem: &str) -> Result<String, &'static str> {
    let bytes = stem.as_bytes();
    if bytes.is_empty()
        || bytes.len() > 64
        || !bytes[0].is_ascii_alphanumeric()
        || !bytes
            .iter()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'_' | b'.' | b'-'))
    {
        return Err("A literal service unit stem is required");
    }
    Ok(format!("{}.service", stem.to_ascii_lowercase()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::Command;

    fn strings(values: &[&str]) -> Vec<String> {
        values.iter().map(|s| (*s).to_owned()).collect()
    }
    fn capture(values: &[String], nested: bool) -> Vec<u8> {
        let mut args = strings(&["/bin/sh", "-c", "printf '%s\\0' \"$@\"", "fixture"]);
        args.extend_from_slice(values);
        let command = join(&args).unwrap();
        let command = if nested {
            join(&strings(&["/bin/sh", "-c", &command])).unwrap()
        } else {
            command
        };
        let output = Command::new("/bin/sh")
            .args(["-c", &command])
            .env_clear()
            .env("PATH", "/usr/bin:/bin")
            .output()
            .unwrap();
        assert!(output.status.success());
        output.stdout
    }
    #[test]
    fn literal_argv_round_trips_direct_and_nested_shell_layers() {
        let args = strings(&[
            "",
            "simple",
            "two words",
            "single'quote",
            "\"double\"",
            "$HOME",
            "$(printf INJECTED)",
            "`printf INJECTED`",
            "line\nbreak",
            "; : #",
            "*?[x]",
            "\\",
            "-n",
            "İstanbul 🦀",
        ]);
        let expected = args
            .iter()
            .flat_map(|s| s.as_bytes().iter().copied().chain([0]))
            .collect::<Vec<_>>();
        assert_eq!(capture(&args, false), expected);
        assert_eq!(capture(&args, true), expected);
    }
    #[test]
    fn empty_command_and_nul_fail_closed_but_empty_data_is_valid() {
        assert!(join(&[]).is_err());
        assert!(join(&strings(&[""])).is_err());
        assert!(join(&strings(&["echo", "a\0b"])).is_err());
        assert!(join(&strings(&["e\0cho"])).is_err());
        assert_eq!(quote("").unwrap(), "''");
    }
    #[test]
    fn shell_operators_cannot_create_injection_sentinel() {
        let dir = std::env::temp_dir().join(format!("fildesk-shell-{}", std::process::id()));
        std::fs::create_dir(&dir).unwrap();
        let sentinel = dir.join("unexpected");
        let p = sentinel.to_str().unwrap();
        let values = vec![
            format!("; touch {p}; #"),
            format!("$(touch {p})"),
            format!("`touch {p}`"),
            format!("' ; touch {p}; #"),
            format!("\n touch {p}\n"),
        ];
        let _ = capture(&values, false);
        let _ = capture(&values, true);
        assert!(!sentinel.exists());
        std::fs::remove_dir(dir).unwrap();
    }
    #[test]
    fn trusted_script_is_explicit_and_preserves_path_execution() {
        // No sudo: explicit sh -c is tested with an unprivileged fixed printf.
        let args = strings(&["/bin/sh", "-c", "printf '%s' 'trusted; literal'", "fixture"]);
        let command = join(&args).unwrap();
        let output = Command::new("/bin/sh")
            .args(["-c", &command])
            .env_clear()
            .env("PATH", "/usr/bin:/bin")
            .output()
            .unwrap();
        assert!(output.status.success());
        assert_eq!(output.stdout, b"trusted; literal");
        let literal = strings(&["printf", "%s", "trusted; literal"]);
        let output = Command::new("/bin/sh")
            .args(["-c", &join(&literal).unwrap()])
            .env_clear()
            .env("PATH", "/usr/bin:/bin")
            .output()
            .unwrap();
        assert!(output.status.success());
        assert_eq!(output.stdout, b"trusted; literal");
    }
    #[test]
    fn service_stems_have_bounded_literal_grammar_and_controlled_suffix() {
        assert_eq!(service_unit("fildesk").unwrap(), "fildesk.service");
        assert_eq!(service_unit("FilDesk").unwrap(), "fildesk.service");
        assert_eq!(service_unit("rustdesk").unwrap(), "rustdesk.service");
        assert!(service_unit(&"a".repeat(64)).is_ok());
        for bad in [
            "",
            "-option",
            ".hidden",
            "a/b",
            "a\\b",
            "*",
            "a?",
            "[ab]",
            "a b",
            "a\nb",
            "a\0b",
            "İstanbul",
            "a@b",
            "a:b",
        ] {
            assert!(service_unit(bad).is_err(), "invalid stem accepted");
        }
        assert!(service_unit(&"a".repeat(65)).is_err());
    }
}
