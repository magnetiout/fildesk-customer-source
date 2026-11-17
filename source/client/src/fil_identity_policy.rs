//! Proposed fixed-deployment policy; no crypto, networking or side effects.
pub fn fixed_sg(profile: &str, environment: &str, id_server: &str, relay: &str) -> bool {
    matches!(profile, "customer" | "operator")
        && matches!(environment, "staging" | "production")
        && id_server == "129.212.237.210:21116"
        && relay == "129.212.237.210:21117"
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn fixed_both_roles_and_environments() {
        for role in ["customer", "operator"] {
            for env in ["staging", "production"] {
                assert!(fixed_sg(
                    role,
                    env,
                    "129.212.237.210:21116",
                    "129.212.237.210:21117"
                ));
            }
        }
    }
    #[test]
    fn generic_and_loopback_unchanged() {
        assert!(!fixed_sg(
            "customer",
            "development",
            "127.0.0.1:21116",
            "127.0.0.1:21117"
        ));
        assert!(!fixed_sg(
            "unknown",
            "staging",
            "129.212.237.210:21116",
            "129.212.237.210:21117"
        ));
        assert!(!fixed_sg(
            "operator",
            "production",
            "example.com:21116",
            "129.212.237.210:21117"
        ));
    }
}

/// Only FiL's newly introduced bounded-stage failures; upstream errors keep their wording.
pub fn connection_error_message(code: &str) -> Option<&'static str> {
    match code {
        "FIL_IDENTITY_ROOT_CONFIGURATION_MISMATCH" | "FIL_IDENTITY_ROOT_INVALID" =>
            Some("Sunucu anahtarı yapılandırması doğrulanamadı. FiL destek ekibiyle iletişime geçin."),
        "FIL_PEER_IDENTITY_UNVERIFIED" | "FIL_PEER_IDENTITY_ID_MISMATCH" |
        "FIL_PEER_SIGNATURE_INVALID" | "FIL_PEER_HANDSHAKE_MESSAGE_INVALID" |
        "FIL_PEER_HANDSHAKE_MALFORMED" | "FIL_SECURE_SESSION_REQUIRED" =>
            Some("Uzak cihazın kimliği doğrulanamadı. Güvenli bağlantı kurulamadığı için işlem durduruldu."),
        "FIL_NATIVE_PHASE_OPERATION_TIMEOUT" =>
            Some("Bağlantı aşaması zamanında tamamlanamadı. Yeni bir bağlantı başlatın."),
        _ => None,
    }
}

#[cfg(test)]
mod message_tests {
    #[test]
    fn new_failures_are_actionable_and_legacy_messages_stay_unchanged() {
        assert!(super::connection_error_message("FIL_PEER_IDENTITY_UNVERIFIED").unwrap().contains("kimliği doğrulanamadı"));
        assert!(super::connection_error_message("FIL_NATIVE_PHASE_OPERATION_TIMEOUT").unwrap().contains("Yeni bir bağlantı"));
        assert_eq!(super::connection_error_message("Upstream connection error"), None);
    }
}
