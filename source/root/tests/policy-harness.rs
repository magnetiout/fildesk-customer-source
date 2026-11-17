#[path = "../client/src/fil_build_config.rs"]
mod fil_build_config;
#[path = "../client/src/fil_remote.rs"]
mod fil_remote;

#[test]
fn fil_support_policy_applies_to_real_upstream_config() {
    use hbb_common::{config::{self, Config}, password_security};
    assert!(fil_remote::initialize());
    let customer = fil_build_config::PROFILE == "customer";
    assert_eq!(config::is_disable_installation(), !customer);
    assert_eq!(Config::is_disable_change_permanent_password(), !customer);
    assert!(!Config::has_permanent_password());
    assert!(!Config::is_using_preset_password());
    assert!(config::is_disable_account());
    assert!(Config::no_register_device());
    assert!(password_security::temporary_enabled());
    assert_eq!(password_security::permanent_enabled(), customer);
    assert_eq!(password_security::temporary_password_length(), 10);
    assert_eq!(Config::get_option("custom-rendezvous-server"), fil_build_config::ID_SERVER);
    assert_eq!(Config::get_option("key"), fil_build_config::PUBLIC_KEY);
    Config::set_option("verification-method".into(), "use-permanent-password".into());
    assert_eq!(password_security::permanent_enabled(), customer);
    if customer {
        assert!(!password_security::temporary_enabled());
        Config::set_option("verification-method".into(), "use-both-passwords".into());
        assert!(password_security::temporary_enabled());
        // Ephemeral per-test value, never shipped as a credential.
        let password = Config::get_auto_password(24);
        assert!(Config::set_permanent_password(&password));
        assert!(Config::has_local_permanent_password());
        assert!(Config::set_permanent_password(""));
        assert!(!Config::has_permanent_password());
    }
    assert!(!Config::get_bool_option("allow-hide-cm"));
    for key in ["enable-file-transfer", "enable-clipboard"] {
        assert_eq!(Config::get_bool_option(key), customer);
        Config::set_option(key.into(), if customer { "N" } else { "Y" }.into());
        assert_eq!(Config::get_bool_option(key), !customer);
    }
    assert!(!Config::get_bool_option("enable-audio"));
    Config::set_option("enable-audio".into(), "Y".into());
    assert!(Config::get_bool_option("enable-audio"));
    assert!(!config::allow_insecure_tls_fallback());
    Config::set_option("access-mode".into(), "full".into());
    assert_eq!(Config::get_option("access-mode"), "custom");
    for key in ["enable-privacy-mode", "enable-block-input", "enable-camera", "enable-remote-restart", "enable-record-session"] {
        assert!(!Config::get_bool_option(key));
    }
    assert_eq!(fil_build_config::ENVIRONMENT, "development");
    assert_eq!(config::is_incoming_only(), fil_build_config::PROFILE == "customer");
}
