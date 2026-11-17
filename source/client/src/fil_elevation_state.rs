//! Observation of one locally consented portable helper request; never grants session access.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Phase { Standard, Requested, WaitingLocalApproval, HelperStarting, Active, Declined, Cancelled, TimedOut, Failed }
impl Phase {
 pub fn label(self) -> &'static str { match self {
 Self::Standard=>"standard", Self::Requested=>"requested", Self::WaitingLocalApproval=>"waiting_local_approval", Self::HelperStarting=>"helper_starting", Self::Active=>"active", Self::Declined=>"declined", Self::Cancelled=>"cancelled", Self::TimedOut=>"timed_out", Self::Failed=>"failed" } }
 pub fn pending(self)->bool { matches!(self,Self::Requested|Self::WaitingLocalApproval|Self::HelperStarting) }
}
pub struct State { pub generation:u64, pub phase:Phase, pub error_code:Option<i32> }
impl Default for State { fn default()->Self {Self{generation:0,phase:Phase::Standard,error_code:None}} }
impl State {
 pub fn begin(&mut self,generation:u64)->bool { if generation<=self.generation || self.phase.pending() || self.phase==Phase::Active {return false} self.generation=generation;self.phase=Phase::Requested;self.error_code=None;true }
 pub fn update(&mut self,generation:u64,phase:Phase)->bool { if generation!=self.generation || !self.phase.pending() {return false} self.phase=phase;true }
 pub fn lost(&mut self,generation:u64) {if self.generation==generation && self.phase==Phase::Active {self.phase=Phase::Failed;}}
}
#[cfg(test)] mod tests {
 use super::*;
 #[test]fn local_request_does_not_imply_capability(){let mut s=State::default();assert!(s.begin(1));assert!(s.update(1,Phase::WaitingLocalApproval));assert_ne!(s.phase,Phase::Active);assert!(s.update(1,Phase::HelperStarting));assert!(s.update(1,Phase::Active));assert!(!s.begin(2));s.lost(1);assert_eq!(s.phase,Phase::Failed);}
 #[test]fn cancelled_timeout_decline_reject_late_ack_and_allow_deliberate_retry(){for terminal in [Phase::Cancelled,Phase::TimedOut,Phase::Declined,Phase::Failed]{let mut s=State::default();assert!(s.begin(1));assert!(!s.begin(2));assert!(s.update(1,terminal));assert!(!s.update(1,Phase::Active));assert!(s.begin(2));assert!(!s.update(1,Phase::Active));assert!(s.update(2,Phase::Active));}}
 #[test]fn duplicate_and_cross_request_ack_are_rejected(){let mut s=State::default();assert!(s.begin(2));assert!(!s.update(1,Phase::Active));assert!(s.update(2,Phase::Active));assert!(!s.update(2,Phase::Active));}
}
