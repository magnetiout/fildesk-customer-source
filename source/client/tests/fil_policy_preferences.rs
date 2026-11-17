//! Real native Config and production policy; no application profile is read.
#[path = "../src/fil_remote.rs"]
mod fil_remote;
#[path = "../src/fil_support_consent.rs"]
mod fil_support_consent;
#[path = "../src/fil_identity_policy.rs"]
mod fil_identity_policy;
mod fil_build_config {
    pub const PROFILE: &str = env!("FIL_POLICY_PROFILE");
    pub const APP_NAME: &str = "FilDesk-Policy-Test";
    pub const ID_SERVER: &str = "127.0.0.1:21116";
    pub const RELAY_SERVER: &str = "127.0.0.1:21117";
    pub const PUBLIC_KEY: &str = "";
    pub const ENVIRONMENT: &str = "development";
}

#[test]
fn effective_policy_preserves_explicit_preferences_and_secure_defaults() {
    use hbb_common::{config::{self, Config}, password_security as password};
    let permanent = Config::get_auto_password(24);
    assert!(Config::set_permanent_password(&permanent));
    let stored_permanent = Config::get_local_permanent_password_storage_and_salt();
    assert!(fil_remote::initialize());
    assert_eq!(Config::get_option("approve-mode"), "password-click");
    assert_eq!(Config::get_option("verification-method"), "use-temporary-password");
    assert_eq!(password::temporary_password_length(), 6);
    assert!(!Config::get_bool_option("allow-numeric-one-time-password"));
    let original = password::temporary_password();
    assert!(original.len() == 6);
    password::update_temporary_password();
    assert_eq!(password::temporary_password().len(), 6);
    assert!(password::temporary_password() != original);
    for length in ["8", "10"] {
        Config::set_option("temporary-password-length".into(), length.into());
        assert!(fil_remote::initialize());
        assert_eq!(password::temporary_password_length(), length.parse::<usize>().unwrap());
    }
    for mode in ["password", "click", "password-click"] {
        Config::set_option("approve-mode".into(), mode.into());
        assert!(fil_remote::initialize());
        assert_eq!(Config::get_option("approve-mode"), mode);
        assert!(!config::OVERWRITE_SETTINGS.read().unwrap().contains_key("approve-mode"));
    }
    for method in ["use-permanent-password", "use-both-passwords", "use-temporary-password"] {
        Config::set_option("verification-method".into(), method.into());
        assert!(fil_remote::initialize());
        assert_eq!(Config::get_option("verification-method"), method);
        assert_eq!(password::permanent_enabled(), method != "use-temporary-password");
        assert_eq!(password::temporary_enabled(), method != "use-permanent-password");
    }
    assert!(config::is_disable_installation());
    assert!(Config::get_local_permanent_password_storage_and_salt() == stored_permanent);
    assert_eq!(config::is_incoming_only(), fil_build_config::PROFILE == "customer");
    assert_eq!(config::is_outgoing_only(), fil_build_config::PROFILE == "operator");
}
