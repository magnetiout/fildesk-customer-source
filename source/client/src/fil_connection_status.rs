//! Read-only, scoped native evidence. None of these values authorize access.
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    sync::{Mutex, OnceLock},
    time::{Duration, Instant},
};

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Context {
    pub endpoint: String,
    pub key_fingerprint: String,
    pub role: String,
}
pub const BUILD: &str = "1.5.0+77";
pub fn context() -> Context {
    use hbb_common::config::Config;
    Context {
        endpoint: Config::get_option("custom-rendezvous-server"),
        key_fingerprint: crate::common::pk_to_fingerprint(
            crate::decode64(&Config::get_option("key")).unwrap_or_default(),
        ),
        role: crate::fil_build_config::PROFILE.to_owned(),
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ServiceSnapshot {
    #[serde(default)]
    pub build: String,
    pub context: Context,
    pub registration_ack: bool,
    #[serde(default)]
    pub pending_approval: usize,
    pub online: bool,
    pub sessions: Vec<Incoming>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Incoming {
    pub reference: String,
    pub encrypted: bool,
}
static REGISTRATION: OnceLock<Mutex<Option<Context>>> = OnceLock::new();
pub fn registration_reset() {
    *REGISTRATION.get_or_init(Default::default).lock().unwrap() = None;
}
pub fn registration_acknowledged(host: &str) {
    let ctx = context();
    let host_prefix = host.split(':').next().unwrap_or(host);
    let endpoint_prefix = ctx.endpoint.split(':').next().unwrap_or(&ctx.endpoint);
    if ctx.endpoint == host || (!host_prefix.is_empty() && host_prefix == endpoint_prefix) {
        *REGISTRATION.get_or_init(Default::default).lock().unwrap() = Some(ctx);
    }
}
static INCOMING: OnceLock<Mutex<HashMap<i32, (Context, Incoming)>>> = OnceLock::new();
static SERVICE: OnceLock<Mutex<Option<(ServiceSnapshot, Instant)>>> = OnceLock::new();
static PENDING_APPROVAL: OnceLock<Mutex<HashMap<i32, Context>>> = OnceLock::new();
pub fn incoming_pending(id:i32) {
    PENDING_APPROVAL.get_or_init(Default::default).lock().unwrap().insert(id,context());
}
pub fn incoming_authorized(id: i32, encrypted: bool) {
    PENDING_APPROVAL.get_or_init(Default::default).lock().unwrap().remove(&id);
    INCOMING
        .get_or_init(Default::default)
        .lock()
        .unwrap()
        .insert(
            id,
            (
                context(),
                Incoming {
                    reference: format!("incoming-{}", id),
                    encrypted,
                },
            ),
        );
}
pub fn incoming_closed(id: i32) {
    PENDING_APPROVAL.get_or_init(Default::default).lock().unwrap().remove(&id);
    INCOMING
        .get_or_init(Default::default)
        .lock()
        .unwrap()
        .remove(&id);
}
pub fn service_snapshot() -> ServiceSnapshot {
    let ctx = context();
    let live: Vec<_> = crate::server::AUTHED_CONNS
        .lock()
        .unwrap()
        .iter()
        .map(|s| s.conn_id)
        .collect();
    let sessions = INCOMING
        .get_or_init(Default::default)
        .lock()
        .unwrap()
        .iter()
        .filter(|(id, (c, _))| live.contains(id) && c == &ctx)
        .map(|(_, (_, s))| s.clone())
        .collect();
    let pending_approval = PENDING_APPROVAL.get_or_init(Default::default).lock().unwrap().values().filter(|c| **c==ctx).count();
    ServiceSnapshot {
        build: BUILD.to_owned(),
        pending_approval,
        context: ctx,
        registration_ack: hbb_common::config::Config::get_key_confirmed()
            && REGISTRATION
                .get_or_init(Default::default)
                .lock()
                .unwrap()
                .as_ref()
                == Some(&context()),
        online: hbb_common::config::get_online_state() > 0,
        sessions,
    }
}
pub fn receive_service(snapshot: Option<ServiceSnapshot>) {
    *SERVICE.get_or_init(Default::default).lock().unwrap() = snapshot.filter(|s| s.build == BUILD).map(|s| (s, Instant::now()));
}
pub fn cached_service() -> Option<ServiceSnapshot> {
    let mut cached = SERVICE.get_or_init(Default::default).lock().unwrap();
    if cached
        .as_ref()
        .is_some_and(|(s, at)| at.elapsed() >= Duration::from_secs(3) || s.context != context())
    {
        *cached = None;
    }
    cached.as_ref().map(|(s, _)| s.clone())
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct SessionEvidence {
    context: Context,
    round: u32,
    pub reference: String,
    pub phase: &'static str,
    pub encrypted: Option<bool>,
    pub peer_identity: &'static str,
    pub direct: Option<bool>,
    pub stream_type: String,
}
impl SessionEvidence {
    pub fn begin(&mut self, round: u32) {
        if !self.phase.is_empty() && round <= self.round {
            return;
        }
        *self = Self {
            context: context(),
            round,
            reference: uuid::Uuid::new_v4().simple().to_string(),
            phase: "requesting",
            peer_identity: "not_evaluated",
            ..Default::default()
        };
    }
    pub fn transport(
        &mut self,
        round: u32,
        encrypted: bool,
        direct: bool,
        stream: &str,
        pinned_identity: bool,
    ) {
        if self.round != round || self.phase != "requesting" {
            return;
        }
        self.phase = "authorization_pending";
        self.encrypted = Some(encrypted);
        self.direct = Some(direct);
        self.stream_type = stream.to_owned();
        // Only pinned FilDesk's fail-closed secure_connection + secured stream proves this claim.
        self.peer_identity = if encrypted && pinned_identity {
            "pinned_root_peer_signature"
        } else {
            "unknown"
        };
    }
    pub fn progress(&mut self, round: u32, phase: &'static str) {
        if self.round != round {
            return;
        }
        if (self.phase == "authorization_pending" && phase == "authorized_waiting_video")
            || (self.phase == "authorized_waiting_video" && phase == "video_packet_received")
        {
            self.phase = phase;
        }
    }
    pub fn verification_failed(&mut self, round: u32) {
        if self.round == round && self.phase == "requesting" {
            self.phase = "verification_failed";
            self.peer_identity = "failed";
            self.encrypted = None;
        }
    }
    pub fn close(&mut self, round: u32) {
        if self.round != round {
            return;
        }
        if matches!(self.phase, "verification_failed" | "configuration_failed") {
            return;
        }
        self.phase = "ended";
        self.encrypted = None;
        self.peer_identity = "stale";
        self.direct = None;
        self.stream_type.clear();
    }
    pub fn configuration_failed(&mut self, round: u32) {
        if self.round == round && self.phase == "requesting" {
            self.phase = "configuration_failed";
        }
    }
    pub fn current(&mut self) -> bool {
        if self.context != context() {
            self.phase = "ended";
            self.encrypted = None;
            self.peer_identity = "stale";
            self.direct = None;
        }
        !self.phase.is_empty() && self.phase != "ended"
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn native_round_scopes_transport_authorization_and_packet_evidence() {
        let mut s = SessionEvidence::default();
        s.begin(1);
        s.transport(1, true, false, "TCP", true);
        assert_eq!(s.peer_identity, "pinned_root_peer_signature");
        assert_eq!(s.phase, "authorization_pending");
        s.progress(1, "video_packet_received");
        assert_eq!(s.phase, "authorization_pending");
        s.progress(1, "authorized_waiting_video");
        s.progress(1, "video_packet_received");
        assert_eq!(s.phase, "video_packet_received");
        s.begin(1);
        assert_eq!(s.phase, "video_packet_received");
        s.close(1);
        assert!(!s.current());
        assert_eq!(s.encrypted, None);
        s.progress(1, "authorized_waiting_video");
        assert_eq!(s.phase, "ended");
        s.begin(2);
        s.transport(1, true, true, "TCP", true);
        assert_eq!(s.encrypted, None);
        s.transport(2, false, true, "TCP", false);
        assert_eq!(s.peer_identity, "unknown");
        s.close(1);
        assert_eq!(s.phase, "authorization_pending");
    }

    #[test]
    fn native_serialized_boundary_fixtures() {
        assert!(include_str!("../flutter/pubspec.yaml").contains(&format!("version: {}", BUILD)));
        let ctx = context();
        let mut snapshots = Vec::new();
        let mut state = SessionEvidence::default();
        state.begin(7);
        for step in 0..5 {
            match step {
                1 => state.transport(7, true, false, "TCP", true),
                2 => state.progress(7, "authorized_waiting_video"),
                3 => state.progress(7, "video_packet_received"),
                4 => state.close(7),
                _ => (),
            }
            snapshots.push(serde_json::json!({"version":1,"build":BUILD,"context":ctx,
                "service":null,"outgoing":if state.current() { vec![state.clone()] } else { vec![] }}));
        }
        state.begin(8);
        state.verification_failed(8);
        state.close(8);
        assert_eq!(state.phase, "verification_failed");
        assert_eq!(state.encrypted, None);
        state.begin(9);
        state.configuration_failed(9);
        state.close(9);
        assert_eq!(state.phase, "configuration_failed");
        if let Ok(path) = std::env::var("FIL_STATUS_FIXTURES") {
            std::fs::write(path, serde_json::to_vec_pretty(&snapshots).unwrap()).unwrap();
        }
        assert_eq!(
            snapshots[1]["outgoing"][0]["peer_identity"],
            "pinned_root_peer_signature"
        );
        assert!(snapshots[4]["outgoing"].as_array().unwrap().is_empty());
    }
    #[test]
    fn authoritative_service_snapshot_expires_and_old_configuration_is_unknown() {
        let snapshot = service_snapshot();
        receive_service(Some(snapshot.clone()));
        assert!(cached_service().is_some());
        let mut changed = snapshot.clone();
        changed.context.key_fingerprint.push_str("changed");
        receive_service(Some(changed));
        assert!(cached_service().is_none());
        *SERVICE.get_or_init(Default::default).lock().unwrap() =
            Some((snapshot, Instant::now() - Duration::from_secs(4)));
        assert!(cached_service().is_none());
        receive_service(None);
        assert!(cached_service().is_none());
    }

    #[test]
    fn configuration_and_sessions_do_not_share_trust() {
        let mut a = SessionEvidence::default();
        a.begin(5);
        a.transport(5, true, true, "TCP", true);
        let mut b = SessionEvidence::default();
        b.begin(5);
        assert_ne!(a.reference, b.reference);
        assert_eq!(b.encrypted, None);
        assert!(a.current());
        a.context.endpoint.push_str("-changed");
        assert!(!a.current());
        b.context.key_fingerprint.push_str("-changed");
        assert!(!b.current());
    }
}
