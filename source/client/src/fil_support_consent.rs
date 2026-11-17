//! Connection-local customer consent. This does not identify a managed operator.
#[derive(Default, Debug)]
pub(crate) struct CustomerConsent {
    credential_verified: bool,
    locally_approved: bool,
}
impl CustomerConsent {
    pub(crate) fn reset(&mut self) {
        *self = Self::default();
    }
    pub(crate) fn credential_verified(&mut self) {
        self.credential_verified = true;
    }
    pub(crate) fn has_verified_credential(&self) -> bool {
        self.credential_verified
    }
    pub(crate) fn approve_locally(&mut self) -> bool {
        self.locally_approved = true;
        true
    }
    pub(crate) fn may_authorize(&self) -> bool {
        self.credential_verified || self.locally_approved
    }
}
/// Unknown build profiles inherit the restrictive customer policy.
pub(crate) fn customer_policy(profile: &str) -> bool {
    profile != "operator"
}
pub(crate) fn customer_disallowed_command(argument: &str) -> bool {
    matches!(
        argument,
        "--install"
            | "--silent-install"
            | "--install-service"
            | "--service"
            | "--run-as-system"
            | "--elevate"
            | "--update"
            | "--after-install"
            | "--before-uninstall"
            | "--uninstall"
            | "--uninstall-service"
            | "--install-idd"
            | "--portable-service"
            | "--uninstall-amyuni-idd"
            | "--install-remote-printer"
            | "--uninstall-remote-printer"
            | "--uninstall-cert"
    ) || argument.starts_with("--portable-service-shmem-name")
}

/// The portable helper is the only privileged Customer entrypoint. Its
/// privilege and IPC token checks still run in the Windows launcher and helper.
pub(crate) fn customer_scoped_portable_helper_command(arguments: &[String]) -> bool {
    fn valid_shmem(argument: &str) -> bool {
        let Some(name) = argument.strip_prefix("--portable-service-shmem-name=") else {
            return false;
        };
        !name.is_empty()
            && name.len() <= 64
            && name
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_' || byte == b'-')
    }

    match arguments {
        [portable, shmem, elevate] => {
            portable == "--portable-service"
                && valid_shmem(shmem)
                && elevate == "--elevate"
        }
        [portable_or_system, shmem] => {
            (portable_or_system == "--portable-service" || portable_or_system == "--run-as-system")
                && valid_shmem(shmem)
        }
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn password_or_current_local_consent_authorizes_only_this_connection() {
        let mut state = CustomerConsent::default();
        assert!(!state.may_authorize());
        state.credential_verified();
        assert!(state.may_authorize());
        assert!(state.has_verified_credential());
        let mut manual = CustomerConsent::default();
        assert!(manual.approve_locally());
        assert!(manual.may_authorize());
        assert!(!manual.has_verified_credential());
    }
    #[test]
    fn retry_and_new_connection_do_not_inherit_consent() {
        let mut state = CustomerConsent::default();
        state.credential_verified();
        state.approve_locally();
        state.reset();
        assert!(!state.may_authorize());
        assert!(!CustomerConsent::default().may_authorize());
    }
    #[test]
    fn restrictive_profile_and_command_boundary() {
        assert!(customer_policy("customer"));
        assert!(customer_policy(""));
        assert!(!customer_policy("operator"));
        for argument in [
            "--install",
            "--silent-install",
            "--install-service",
            "--service",
            "--run-as-system",
            "--elevate",
            "--update",
            "--after-install",
            "--before-uninstall",
            "--uninstall",
            "--uninstall-service",
            "--install-idd",
            "--portable-service",
            "--uninstall-amyuni-idd",
            "--install-remote-printer",
            "--uninstall-remote-printer",
            "--uninstall-cert",
            "--portable-service-shmem-name=unexpected",
        ] {
            assert!(customer_disallowed_command(argument));
        }
        // The portable user's ordinary runtime is not an installed OS service.
        for argument in ["--server", "--tray", "--cm", "--version"] {
            assert!(!customer_disallowed_command(argument));
        }
    }

    #[test]
    fn only_exact_scoped_customer_helper_commands_pass() {
        let allowed = [
            vec!["--portable-service", "--portable-service-shmem-name=_portable_service_42_ab12", "--elevate"],
            vec!["--run-as-system", "--portable-service-shmem-name=_portable_service_42_ab12"],
            vec!["--portable-service", "--portable-service-shmem-name=_portable_service_42_ab12"],
        ];
        for arguments in allowed {
            assert!(customer_scoped_portable_helper_command(
                &arguments.into_iter().map(str::to_owned).collect::<Vec<_>>()
            ));
        }
        let denied = [
            vec!["--portable-service"],
            vec!["--run-as-system"],
            vec!["--portable-service", "--portable-service-shmem-name=../escape", "--elevate"],
            vec!["--portable-service", "--portable-service-shmem-name=_portable_service_42_ab12", "--elevate", "--install"],
            vec!["--portable-service", "--portable-service-shmem-name=_portable_service_42_ab12", "--run-as-system"],
            vec!["--elevate", "--portable-service-shmem-name=_portable_service_42_ab12"],
            vec!["--portable-service", "--portable-service-shmem-name=_portable_service_42_ab12", "--elevate", "--elevate"],
            vec!["--run-as-system", "--portable-service-shmem-name=_portable_service_42_ab12", "--install"],
            vec!["--portable-service", "--portable-service-shmem-name=", "--elevate"],
            vec!["--portable-service", "--portable-service-shmem-name="],
            vec!["--run-as-system", "--portable-service-shmem-name="],
        ];
        for arguments in denied {
            assert!(!customer_scoped_portable_helper_command(
                &arguments.into_iter().map(str::to_owned).collect::<Vec<_>>()
            ));
        }
    }
}
