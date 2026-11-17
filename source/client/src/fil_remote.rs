//! FilDesk OSS policy. No Pro configuration signature or licensing bypass.
use hbb_common::config;
use crate::fil_build_config as build;

pub fn initialize() -> bool {
    *config::APP_NAME.write().unwrap() = build::APP_NAME.to_owned();
    *config::PROD_RENDEZVOUS_SERVER.write().unwrap() = build::ID_SERVER.to_owned();
    let customer = requires_customer_consent();
    let mut options = config::OVERWRITE_SETTINGS.write().unwrap();
    for (key, value) in [
        ("custom-rendezvous-server", build::ID_SERVER),
        ("relay-server", build::RELAY_SERVER),
        ("key", build::PUBLIC_KEY),
        ("api-server", ""),
        ("access-mode", "custom"),
        ("enable-privacy-mode", "N"),
        ("enable-block-input", "N"),
        ("enable-camera", "N"),
        ("enable-remote-restart", "N"),
        ("enable-record-session", "N"),
        ("allow-hide-cm", "N"),
        ("allow-auto-record-incoming", "N"),
        ("allow-auto-record-outgoing", "N"),
        ("allow-auto-update", "N"),
        ("allow-remote-config-modification", "N"),
        ("allow-insecure-tls-fallback", "N"),
        ("allow-numeric-one-time-password", "N"),
        ("enable-lan-discovery", "N"),
        ("direct-server", "N"),
        ("enable-tunnel", "N"),
        ("enable-terminal", "N"),
    ] {
        options.insert(key.to_owned(), value.to_owned());
    }
    if customer { options.insert("enable-trusted-devices".into(), "N".into()); }
    drop(options);
    let mut defaults = config::DEFAULT_SETTINGS.write().unwrap();
    for (key, value) in [
        ("temporary-password-length", "6"),
        ("approve-mode", "password-click"),
        ("verification-method", "use-temporary-password"),
        ("enable-file-transfer", if customer { "Y" } else { "N" }),
        ("enable-clipboard", if customer { "Y" } else { "N" }),
        ("enable-audio", "N"),
    ] {
        defaults.insert(key.to_owned(), value.to_owned());
    }
    drop(defaults);
    let mut local = config::OVERWRITE_LOCAL_SETTINGS.write().unwrap();
    local.insert("enable-check-update".to_owned(), "N".to_owned());
    drop(local);
    config::DEFAULT_LOCAL_SETTINGS.write().unwrap().insert("lang".to_owned(), "tr".to_owned());
    let mut hard = config::HARD_SETTINGS.write().unwrap();
    for key in ["disable-account", "disable-ab"] {
        hard.insert(key.to_owned(), "Y".to_owned());
    }
    hard.insert("disable-installation".into(), "Y".into());
    hard.insert("conn-type".to_owned(), if customer { "incoming" } else { "outgoing" }.to_owned());
    drop(hard);
    let mut builtin = config::BUILTIN_SETTINGS.write().unwrap();
    for key in ["hide-network-settings", "hide-server-settings", "hide-proxy-settings", "hide-websocket-settings"] {
        builtin.insert(key.to_owned(), "Y".to_owned());
    }
    for key in ["register-device", "allow-logon-screen-password", "allow-deep-link-password", "allow-deep-link-server-settings", "allow-remote-cm-modification"] {
        builtin.insert(key.to_owned(), "N".to_owned());
    }
    builtin.insert("hide-help-cards".into(), if customer { "N" } else { "Y" }.into());
    builtin.insert("disable-change-permanent-password".into(), "Y".into());
    true
}

/// Fixed accepted Singapore deployment only; generic/development profiles stay compatible.
pub fn requires_pinned_identity() -> bool {
    crate::fil_identity_policy::fixed_sg(build::PROFILE, build::ENVIRONMENT, build::ID_SERVER, build::RELAY_SERVER)
}

/// User-facing brand only; the configuration/service namespace stays unchanged.
pub fn display_name() -> &'static str {
    if build::PROFILE == "operator" { "FilDesk Operator" } else { "FilDesk" }
}

/// Customer and unknown profiles require connection-local consent and portable operation.
pub fn requires_customer_consent() -> bool {
    crate::fil_support_consent::customer_policy(build::PROFILE)
}
