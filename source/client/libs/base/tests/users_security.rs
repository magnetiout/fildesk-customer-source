#![cfg(target_os = "linux")]
use std::{collections::BTreeSet, ffi::CString};
use users::{get_current_uid, get_user_by_uid, os::unix::UserExt};

#[test]
fn uid_home_and_missing_account_remain_os_derived() {
    let uid = unsafe { libc::getuid() };
    assert_eq!(get_current_uid(), uid);
    let account = get_user_by_uid(uid).expect("current account must exist in this fixture");
    assert_eq!(account.uid(), uid);
    assert!(account.home_dir().is_absolute());
    assert!(get_user_by_uid(libc::uid_t::MAX).is_none());
}

#[test]
fn supplementary_groups_match_libc_without_spurious_root() {
    let mut raw = vec![0 as libc::gid_t; 1024];
    let count = unsafe { libc::getgroups(raw.len() as i32, raw.as_mut_ptr()) };
    assert!(count >= 0);
    raw.truncate(count as usize);
    let expected: BTreeSet<_> = raw
        .into_iter()
        .filter(|gid| users::get_group_by_gid(*gid).is_some())
        .collect();
    let actual: BTreeSet<_> = users::group_access_list()
        .unwrap()
        .into_iter()
        .map(|group| group.gid())
        .collect();
    assert_eq!(actual, expected);

    let account = get_user_by_uid(get_current_uid()).unwrap();
    let name = CString::new(account.name().as_encoded_bytes()).unwrap();
    let mut raw = vec![0 as libc::gid_t; 1024];
    let mut count = raw.len() as i32;
    assert!(
        unsafe {
            libc::getgrouplist(
                name.as_ptr(),
                account.primary_group_id(),
                raw.as_mut_ptr(),
                &mut count,
            )
        } >= 0
    );
    raw.truncate(count as usize);
    let expected: BTreeSet<_> = raw
        .into_iter()
        .filter(|gid| users::get_group_by_gid(*gid).is_some())
        .collect();
    let actual: BTreeSet<_> = users::get_user_groups(account.name(), account.primary_group_id())
        .unwrap()
        .into_iter()
        .map(|group| group.gid())
        .collect();
    assert_eq!(actual, expected);
}
