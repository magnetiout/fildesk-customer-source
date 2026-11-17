//! Proposed, std-only progress deadline. Packet liveness MUST NOT renew it.
//! All `now_ms` values are from one monotonic attempt-local origin; never wall time.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Phase {
    AuthConsent,
    FirstVideo,
    FirstPresentation,
    PacketObserved,
    Active,
    Cancelled,
    Expired,
}
#[derive(Clone, Copy, Debug)]
pub struct Limits {
    pub auth_ms: u64,
    pub video_ms: u64,
    pub presentation_ms: Option<u64>,
}
#[derive(Clone, Copy, Debug)]
pub struct Deadline {
    generation: u64,
    phase: Phase,
    deadline_ms: u64,
    last_now_ms: u64,
    limits: Limits,
    expired_phase: Option<Phase>,
}
impl Deadline {
    pub fn new(generation: u64, now_ms: u64, limits: Limits) -> Self {
        Self {
            generation,
            phase: Phase::AuthConsent,
            deadline_ms: now_ms.saturating_add(limits.auth_ms),
            last_now_ms: now_ms,
            limits,
            expired_phase: None,
        }
    }
    pub fn phase(&self) -> Phase {
        self.phase
    }
    pub fn expired_phase(&self) -> Option<Phase> {
        self.expired_phase
    }
    fn bounded(&self) -> bool {
        matches!(
            self.phase,
            Phase::AuthConsent | Phase::FirstVideo | Phase::FirstPresentation
        )
    }
    pub fn remaining_ms(&self, now_ms: u64) -> Option<u64> {
        self.bounded().then(|| {
            self.deadline_ms
                .saturating_sub(now_ms.max(self.last_now_ms))
        })
    }
    pub fn poll(&mut self, generation: u64, now_ms: u64) -> Option<Phase> {
        if generation != self.generation {
            return None;
        }
        self.last_now_ms = self.last_now_ms.max(now_ms);
        if self.bounded() && self.last_now_ms >= self.deadline_ms {
            self.expired_phase = Some(self.phase);
            self.phase = Phase::Expired;
        }
        self.expired_phase
    }
    fn enter(&mut self, phase: Phase, ms: u64) {
        self.phase = phase;
        self.deadline_ms = self.last_now_ms.saturating_add(ms);
    }
    pub fn peer_info(&mut self, generation: u64, now_ms: u64) -> bool {
        if generation != self.generation
            || self.poll(generation, now_ms).is_some()
            || self.phase != Phase::AuthConsent
        {
            return false;
        }
        self.enter(Phase::FirstVideo, self.limits.video_ms);
        true
    }
    pub fn video_packet(&mut self, generation: u64, now_ms: u64) -> bool {
        if generation != self.generation
            || self.poll(generation, now_ms).is_some()
            || self.phase != Phase::FirstVideo
        {
            return false;
        }
        if let Some(ms) = self.limits.presentation_ms {
            self.enter(Phase::FirstPresentation, ms);
        } else {
            self.phase = Phase::PacketObserved;
        }
        true
    }
    /// Only call after an explicit, generation-bound successful renderer acknowledgement.
    pub fn presented(&mut self, generation: u64, now_ms: u64) -> bool {
        if generation != self.generation
            || self.poll(generation, now_ms).is_some()
            || self.phase != Phase::FirstPresentation
        {
            return false;
        }
        self.phase = Phase::Active;
        true
    }
    pub fn cancel(&mut self, generation: u64) -> bool {
        if generation != self.generation || matches!(self.phase, Phase::Cancelled | Phase::Expired)
        {
            return false;
        }
        self.phase = Phase::Cancelled;
        true
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn limits(p: Option<u64>) -> Limits {
        Limits {
            auth_ms: 100,
            video_ms: 30,
            presentation_ms: p,
        }
    }
    #[test]
    fn keepalives_cannot_renew_auth() {
        let mut d = Deadline::new(7, 0, limits(None));
        for n in 1..100 {
            assert_eq!(d.poll(7, n), None);
        }
        assert_eq!(d.poll(7, 100), Some(Phase::AuthConsent));
    }
    #[test]
    fn duplicate_peer_info_cannot_renew_video() {
        let mut d = Deadline::new(7, 0, limits(None));
        assert!(d.peer_info(7, 10));
        assert!(!d.peer_info(7, 39));
        assert_eq!(d.poll(7, 40), Some(Phase::FirstVideo));
    }
    #[test]
    fn raw_packet_is_not_active() {
        let mut d = Deadline::new(7, 0, limits(None));
        d.peer_info(7, 1);
        assert!(d.video_packet(7, 2));
        assert_eq!(d.phase(), Phase::PacketObserved);
        assert!(!d.presented(7, 3));
    }
    #[test]
    fn raw_packet_without_decode_or_ack_expires() {
        let mut d = Deadline::new(7, 0, limits(Some(15)));
        d.peer_info(7, 1);
        d.video_packet(7, 2);
        assert_eq!(d.poll(7, 17), Some(Phase::FirstPresentation));
        assert!(!d.presented(7, 18));
    }
    #[test]
    fn presented_is_explicit_and_stops_deadline() {
        let mut d = Deadline::new(7, 0, limits(Some(15)));
        d.peer_info(7, 1);
        d.video_packet(7, 2);
        assert!(d.presented(7, 16));
        assert_eq!(d.phase(), Phase::Active);
        assert_eq!(d.poll(7, 1_000), None);
    }
    #[test]
    fn wrong_generation_does_not_mutate_clock() {
        let mut d = Deadline::new(7, 0, limits(Some(15)));
        assert_eq!(d.poll(6, u64::MAX), None);
        assert!(!d.peer_info(6, 0));
        assert!(!d.cancel(6));
        assert_eq!(d.remaining_ms(0), Some(100));
    }
    #[test]
    fn stale_events_cannot_revive_cancelled_attempt() {
        let mut d = Deadline::new(7, 0, limits(None));
        assert!(d.cancel(7));
        assert!(!d.peer_info(7, 1));
        assert!(!d.video_packet(7, 2));
        assert_eq!(d.poll(7, 1000), None);
    }
    #[test]
    fn reconnect_is_independent() {
        let mut old = Deadline::new(7, 0, limits(None));
        old.cancel(7);
        let mut new = Deadline::new(8, 0, limits(None));
        assert!(!new.video_packet(7, 2));
        assert!(new.peer_info(8, 2));
        assert_eq!(new.phase(), Phase::FirstVideo);
    }
    #[test]
    fn backward_now_cannot_extend_deadline() {
        let mut d = Deadline::new(7, 0, limits(None));
        d.poll(7, 90);
        assert_eq!(d.remaining_ms(1), Some(10));
        assert_eq!(d.poll(7, 100), Some(Phase::AuthConsent));
    }
    #[test]
    fn overflow_saturates_and_equality_expires() {
        let mut d = Deadline::new(7, u64::MAX - 1, limits(None));
        assert_eq!(d.remaining_ms(u64::MAX - 1), Some(1));
        assert_eq!(d.poll(7, u64::MAX), Some(Phase::AuthConsent));
    }
    #[test]
    fn out_of_order_video_cannot_grant_active() {
        let mut d = Deadline::new(7, 0, limits(Some(15)));
        assert!(!d.video_packet(7, 2));
        assert!(!d.presented(7, 3));
        assert_eq!(d.phase(), Phase::AuthConsent);
    }
    #[test]
    fn zero_budget_is_immediate_timeout() {
        let mut d = Deadline::new(
            7,
            0,
            Limits {
                auth_ms: 0,
                video_ms: 0,
                presentation_ms: None,
            },
        );
        assert!(!d.peer_info(7, 0));
        assert_eq!(d.phase(), Phase::Expired);
    }
}
