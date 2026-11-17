//! Fil portable: immutable embedded inventory, fresh owner-only extraction, held read locks.
use sha2::{Digest,Sha256};
use std::{collections::HashSet,fs::{self,File,OpenOptions},io::{Read,Write},path::{Path,PathBuf}};

// Public application payload only: administrators may read/execute after UAC,
// but receive no write/delete grant. Credentials/settings are never extracted here.
pub const RUNTIME_DACL: &str = "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;OW)(A;OICI;GRGX;;;BA)";
pub fn safe_path(input:&str)->Result<String,String>{
    let value=input.replace('\\',"/");
    let value=value.strip_prefix("./").unwrap_or(&value);
    if value.is_empty() || value.len()>180 {return Err("Invalid payload path length".into())}
    for part in value.split('/') {
        let base=part.split('.').next().unwrap_or("").to_ascii_uppercase();
        if part.is_empty() || part=="." || part==".." || part.ends_with(['.',' ']) ||
            part.bytes().any(|c| !c.is_ascii_alphanumeric() && !b"._- ".contains(&c)) ||
            ["CON","PRN","AUX","NUL","CLOCK$"].contains(&base.as_str()) ||
            (base.len()==4 && (base.starts_with("COM")||base.starts_with("LPT")) && b"123456789".contains(&base.as_bytes()[3])) {
            return Err("Unsafe Windows payload path".into())
        }
    }
    Ok(value.to_string())
}
pub fn hash(bytes:&[u8])->String {format!("{:x}",Sha256::digest(bytes))}
pub fn decode(file:&crate::bin_reader::BinaryData,size:u64,expected:&str)->Result<Vec<u8>,String>{
    if size>256*1024*1024 {return Err("Payload file exceeds limit".into())}
    let mut bytes=Vec::new();
    brotli::Decompressor::new(file.raw,4096).take(size+1).read_to_end(&mut bytes).map_err(|_|"Payload decompression failed")?;
    if bytes.len() as u64!=size || hash(&bytes)!=expected {return Err("Payload SHA256 mismatch".into())}
    Ok(bytes)
}
// Compare the locked file directly, bounded to one small buffer. SHA256 of the
// decoded expected bytes remains mandatory before this exact byte comparison.
pub fn verify_readback<R:Read>(reader:&mut R,expected:&[u8])->Result<(),String>{
    let mut buffer=[0u8;32768];
    for chunk in expected.chunks(buffer.len()) {
        reader.read_exact(&mut buffer[..chunk.len()]).map_err(|_|"Payload readback failed")?;
        if &buffer[..chunk.len()]!=chunk {return Err("Extraction changed before lock".into())}
    }
    let mut extra=[0u8;1];
    if reader.read(&mut extra).map_err(|_|"Payload readback failed")?!=0 {return Err("Extraction changed before lock".into())}
    Ok(())
}
#[cfg(windows)]
mod windows_impl {
    use super::*;
    use crate::startup_timing::{StartupTiming,ExtractionTimings,Phase};
    use std::os::windows::{fs::{OpenOptionsExt,MetadataExt},ffi::OsStrExt};
    use windows::{core::{PCWSTR,w},Win32::{Foundation::{HLOCAL,HWND,LocalFree},Security::{PSECURITY_DESCRIPTOR,SECURITY_ATTRIBUTES,Authorization::*,WinTrust::*},Storage::FileSystem::CreateDirectoryW,System::LibraryLoader::{SetDefaultDllDirectories,SetDllDirectoryW,LOAD_LIBRARY_SEARCH_SYSTEM32,LOAD_LIBRARY_SEARCH_APPLICATION_DIR}}};
    pub mod embedded {include!(concat!(env!("OUT_DIR"),"/fil_payload.rs"));}
    fn wide(path:&Path)->Vec<u16>{path.as_os_str().encode_wide().chain(Some(0)).collect()}
    fn lock(path:&Path,directory:bool)->Result<File,String>{
        let file=OpenOptions::new().read(true).share_mode(1).custom_flags(0x00200000 | if directory {0x02000000}else{0}).open(path).map_err(|_|"Cannot lock extraction path")?;
        let meta=file.metadata().map_err(|_|"Cannot inspect extraction path")?;
        if meta.file_attributes()&0x400!=0 || meta.is_dir()!=directory {return Err("Reparse point/type rejected".into())}
        Ok(file)
    }
    fn private_dir(path:&Path)->Result<(),String>{
        unsafe {
            let mut sd=PSECURITY_DESCRIPTOR::default();
            let descriptor:Vec<u16>=RUNTIME_DACL.encode_utf16().chain(Some(0)).collect();
            ConvertStringSecurityDescriptorToSecurityDescriptorW(PCWSTR(descriptor.as_ptr()),SDDL_REVISION_1,&mut sd,None).map_err(|_|"Private directory ACL failed")?;
            let sa=SECURITY_ATTRIBUTES{nLength:std::mem::size_of::<SECURITY_ATTRIBUTES>() as u32,lpSecurityDescriptor:sd.0,bInheritHandle:false.into()};
            let p=wide(path);let result=CreateDirectoryW(PCWSTR(p.as_ptr()),Some(&sa));
            LocalFree(Some(HLOCAL(sd.0)));
            result.map_err(|_|"Cannot create fresh private directory".into())
        }
    }
    pub fn trust(path:&Path)->Result<(),String>{
        unsafe {
            let name=wide(path);
            let mut info=WINTRUST_FILE_INFO{cbStruct:std::mem::size_of::<WINTRUST_FILE_INFO>() as u32,pcwszFilePath:PCWSTR(name.as_ptr()),..Default::default()};
            let mut data=WINTRUST_DATA{cbStruct:std::mem::size_of::<WINTRUST_DATA>() as u32,dwUIChoice:WTD_UI_NONE,fdwRevocationChecks:WTD_REVOKE_WHOLECHAIN,dwUnionChoice:WTD_CHOICE_FILE,dwStateAction:WTD_STATEACTION_VERIFY,dwProvFlags:WTD_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT,Anonymous:WINTRUST_DATA_0{pFile:&mut info},..Default::default()};
            let mut action=WINTRUST_ACTION_GENERIC_VERIFY_V2;
            let code=WinVerifyTrust(HWND(std::ptr::null_mut()),&mut action,&mut data as *mut _ as _);
            data.dwStateAction=WTD_STATEACTION_CLOSE;
            WinVerifyTrust(HWND(std::ptr::null_mut()),&mut action,&mut data as *mut _ as _);
            if code!=0 {return Err(format!("Windows signature trust failed ({code:#x})"))}
            Ok(())
        }
    }
    // Created suspended, assigned before any application code runs. Descendants
    // remain supervised; abrupt launcher exit terminates this portable process tree.
    struct Handle(windows::Win32::Foundation::HANDLE);
    impl Drop for Handle {fn drop(&mut self){unsafe {let _=windows::Win32::Foundation::CloseHandle(self.0);}}}
    fn quote(value:&str)->String {
        let mut out=String::from("\"");let mut slashes=0;
        for c in value.chars(){
            if c=='\\' {slashes+=1;continue}
            out.extend(std::iter::repeat('\\').take(if c=='"'{slashes*2+1}else{slashes}));slashes=0;out.push(c);
        }
        out.extend(std::iter::repeat('\\').take(slashes*2));out.push('"');out
    }
    fn supervise(exe:&Path,dir:&Path,args:&[String],timing:&StartupTiming)->Result<(),String>{
        use windows::{core::PWSTR,Win32::System::{Threading::*,JobObjects::*}};
        unsafe {
            let job=Handle(CreateJobObjectW(None,PCWSTR::null()).map_err(|_|"Cannot create process job")?);
            let mut limits=JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
            limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            SetInformationJobObject(job.0,JobObjectExtendedLimitInformation,&limits as *const _ as _,std::mem::size_of_val(&limits) as u32).map_err(|_|"Cannot secure process job")?;
            let executable=wide(exe);let directory=wide(dir);
            let line=std::iter::once(exe.to_string_lossy().into_owned()).chain(args.iter().cloned()).map(|s|quote(&s)).collect::<Vec<_>>().join(" ");
            if line.contains('\0'){return Err("Invalid command line".into())}
            let mut line:Vec<u16>=line.encode_utf16().chain(Some(0)).collect();
            let start=STARTUPINFOW{cb:std::mem::size_of::<STARTUPINFOW>() as u32,..Default::default()};
            let mut process=PROCESS_INFORMATION::default();
            CreateProcessW(PCWSTR(executable.as_ptr()),Some(PWSTR(line.as_mut_ptr())),None,None,false,CREATE_SUSPENDED,None,PCWSTR(directory.as_ptr()),&start,&mut process).map_err(|_|"Cannot create verified process")?;
            let process_handle=Handle(process.hProcess);let thread=Handle(process.hThread);
            if AssignProcessToJobObject(job.0,process_handle.0).is_err(){let _=TerminateProcess(process_handle.0,1);return Err("Cannot supervise portable process".into())}
            if ResumeThread(thread.0)==u32::MAX {return Err("Cannot resume portable process".into())}
            // One explicit launch may transfer foreground permission to its own child.
            let _ = winapi::um::winuser::AllowSetForegroundWindow(process.dwProcessId);
            timing.mark(Phase::InnerProcessCreated,0,0);
            loop {
                let mut info=JOBOBJECT_BASIC_ACCOUNTING_INFORMATION::default();
                QueryInformationJobObject(Some(job.0),JobObjectBasicAccountingInformation,&mut info as *mut _ as _,std::mem::size_of_val(&info) as u32,None).map_err(|_|"Cannot monitor portable processes")?;
                if info.ActiveProcesses==0 {break}
                std::thread::sleep(std::time::Duration::from_millis(200));
            }
            Ok(())
        }
    }
    struct Extraction { files:Vec<(PathBuf,File)>,dirs:Vec<(PathBuf,File)>,_ancestors:Vec<File> }
    impl Drop for Extraction {
        fn drop(&mut self){
            // Never recurse through an untrusted path or remove another session's cache.
            while let Some((path,guard))=self.files.pop(){drop(guard);let _=fs::remove_file(path);}
            while let Some((path,guard))=self.dirs.pop(){drop(guard);let _=fs::remove_dir(path);}
        }
    }
    fn extract(reader:crate::bin_reader::BinaryReader,timing:&StartupTiming)->Result<Extraction,String>{
        let base=dirs::data_local_dir().ok_or("LocalAppData unavailable")?;
        let mut extraction=Extraction{files:vec![],dirs:vec![],_ancestors:vec![]};
        let mut ancestors:Vec<_>=base.ancestors().collect();ancestors.reverse();
        for path in ancestors {extraction._ancestors.push(lock(path,true)?);}
        let mut nonce=[0u8;16];getrandom::getrandom(&mut nonce).map_err(|_|"Secure random unavailable")?;
        let suffix=nonce.iter().map(|b|format!("{b:02x}")).collect::<String>();
        let dir=base.join(format!("FilDesk-{}-{suffix}",embedded::PROFILE));
        private_dir(&dir)?;extraction.dirs.push((dir.clone(),lock(&dir,true)?));
        timing.mark(Phase::PrivateDirectoryReady,0,0);
        let mut measured=ExtractionTimings::default();
        let mut names=HashSet::new();let mut total=0u64;
        for file in &reader.files {
            let name=safe_path(&file.path)?;
            if !names.insert(name.to_ascii_lowercase()){return Err("Duplicate payload path".into())}
            let (_,size,digest)=embedded::FILES.iter().find(|(n,_,_)|*n==name).ok_or("Unlisted payload entry")?;
            total=total.checked_add(*size).ok_or("Payload size overflow")?;
            if total>512*1024*1024 {return Err("Payload exceeds total limit".into())}
            let span=timing.span();let bytes=decode(file,*size,digest)?;StartupTiming::add_elapsed(&mut measured.decode_us,span);
            let span=timing.span();
            let mut parent=dir.clone();let parts:Vec<_>=name.split('/').collect();
            for part in &parts[..parts.len()-1] {
                parent.push(part);
                if !extraction.dirs.iter().any(|(p,_)|p==&parent){private_dir(&parent)?;extraction.dirs.push((parent.clone(),lock(&parent,true)?));}
            }
            StartupTiming::add_elapsed(&mut measured.directories_us,span);
            let path=dir.join(&name);
            let span=timing.span();
            // Never truncate/reuse an existing file, even inside this fresh directory.
            let mut writer=OpenOptions::new().write(true).create_new(true).share_mode(1).open(&path).map_err(|_|"Exclusive file creation failed")?;
            writer.write_all(&bytes).map_err(|_|"Payload write failed")?;StartupTiming::add_elapsed(&mut measured.write_us,span);
            let span=timing.span();writer.sync_all().map_err(|_|"Payload flush failed")?;drop(writer);StartupTiming::add_elapsed(&mut measured.flush_us,span);
            let span=timing.span();let mut guard=lock(&path,false)?;verify_readback(&mut guard,&bytes)?;StartupTiming::add_elapsed(&mut measured.readback_us,span);
            let span=timing.span();
            if embedded::REQUIRE_SIGNATURE && (name.to_ascii_lowercase().ends_with(".exe")||name.to_ascii_lowercase().ends_with(".dll")){trust(&path)?;}
            StartupTiming::add_elapsed(&mut measured.signature_us,span);
            extraction.files.push((path,guard));
        }
        timing.extraction(&measured,extraction.files.len(),total);
        timing.mark(Phase::ExtractionVerified,extraction.files.len(),total);
        Ok(extraction)
    }
    pub fn run(reader:crate::bin_reader::BinaryReader,args:Vec<String>,timing:&StartupTiming)->Result<(),String>{
        if reader.exe.replace('\\',"/").trim_start_matches("./")!="FilDesk.exe" {return Err("Unexpected payload entrypoint".into())}
        if reader.files.len()!=embedded::FILES.len(){return Err("Payload inventory mismatch".into())}
        let mut own_guard = None;
        if embedded::REQUIRE_SIGNATURE {
            // Outer signature binds the expected hashes of all signed inner components.
            let own=std::env::current_exe().map_err(|_|"Cannot locate launcher")?;
            own_guard=Some(lock(&own,false)?);trust(&own)?;
        }
        let extraction=extract(reader,timing).map_err(|error|{timing.mark(Phase::ExtractionRejected,0,0);error})?;
        let dir=&extraction.dirs[0].0;
        unsafe {
            SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32|LOAD_LIBRARY_SEARCH_APPLICATION_DIR).map_err(|_|"DLL search hardening failed")?;
            SetDllDirectoryW(w!("")).map_err(|_|"Cannot remove current DLL directory")?;
        }
        let own=std::env::current_exe().map_err(|_|"Launcher identity unavailable")?;
        let mut system=[0u16;32768];
        let size=unsafe {windows::Win32::System::SystemInformation::GetSystemDirectoryW(Some(&mut system))} as usize;
        if size==0 || size>=system.len(){return Err("Windows system directory unavailable".into())}
        let system=String::from_utf16(&system[..size]).map_err(|_|"Invalid system directory")?;
        // These environment changes are confined to this single-threaded launcher.
        std::env::set_var("PATH",system);
        std::env::set_var("RUSTDESK_APPNAME",own.file_name().ok_or("Invalid launcher name")?);
        supervise(&dir.join("FilDesk.exe"),&dir,&args,timing)?;
        timing.mark(Phase::PortableTreeExited,0,0);
        // Read locks cover all non-elevated descendants in the job.
        drop(extraction);drop(own_guard);timing.mark(Phase::CleanupComplete,0,0);Ok(())
    }
    pub fn verify_embedded(blob:&[u8])->Result<(),String>{
        if hash(blob)!=embedded::PAYLOAD_SHA256{return Err("Embedded payload corrupted".into())}Ok(())
    }
    #[cfg(test)] mod tests {
        #[test] fn extraction_locks_and_cleanup(){
            let reader=crate::bin_reader::BinaryReader::new().unwrap();
            let expected=reader.files.len();let extraction=super::extract(reader,&crate::startup_timing::StartupTiming::new()).unwrap();
            let root=extraction.dirs[0].0.clone();assert_eq!(extraction.files.len(),expected);
            assert!(root.file_name().unwrap().to_str().unwrap().starts_with(&format!("FilDesk-{}-",super::embedded::PROFILE)));
            for (path,_) in &extraction.files {
                assert!(std::fs::OpenOptions::new().write(true).open(path).is_err());
                assert!(std::fs::remove_file(path).is_err());
            }
            drop(extraction);assert!(!root.exists());
        }
        #[test] fn job_supervises_native_process(){
            let system=std::path::PathBuf::from(std::env::var_os("SystemRoot").unwrap()).join("System32");
            super::supervise(&system.join("cmd.exe"),&system,&["/d".into(),"/c".into(),"exit /b 0".into()],&crate::startup_timing::StartupTiming::disabled()).unwrap();
        }

        #[test] fn command_line_quotes(){assert_eq!(super::quote("a b"),"\"a b\"");assert_eq!(super::quote("x\\"),"\"x\\\\\"");}
        #[test] fn private_directory_lifecycle(){
            let p=std::env::temp_dir().join(format!("fil-acl-test-{}",std::process::id()));
            super::private_dir(&p).unwrap();assert!(super::private_dir(&p).is_err());
            let guard=super::lock(&p,true).unwrap();assert!(std::fs::rename(&p,p.with_extension("moved")).is_err());drop(guard);std::fs::remove_dir(p).unwrap();
        }
        #[test] fn modified_embedded_payload_rejected(){assert!(super::verify_embedded(b"modified").is_err());}

        use super::*;
        #[test]fn runtime_dacl_does_not_grant_administrators_write() {
            use windows::Win32::Security::{GetSecurityDescriptorDacl,GetAce,IsWellKnownSid,WinBuiltinAdministratorsSid,PSID,ACCESS_ALLOWED_ACE,ACL};
            use windows::Win32::Security::Authorization::ConvertStringSecurityDescriptorToSecurityDescriptorW;
            unsafe {
                let text:Vec<u16>=super::super::RUNTIME_DACL.encode_utf16().chain(Some(0)).collect();
                let mut descriptor=PSECURITY_DESCRIPTOR::default();
                ConvertStringSecurityDescriptorToSecurityDescriptorW(PCWSTR(text.as_ptr()),SDDL_REVISION_1,&mut descriptor,None).unwrap();
                let mut present=false.into();let mut defaulted=false.into();let mut acl:*mut ACL=std::ptr::null_mut();
                GetSecurityDescriptorDacl(descriptor,&mut present,&mut acl,&mut defaulted).unwrap();
                assert!(!acl.is_null());assert_eq!((*acl).AceCount,3);
                let mut ace=std::ptr::null_mut();GetAce(acl,2,&mut ace).unwrap();
                let mask=(*(ace as *const ACCESS_ALLOWED_ACE)).Mask;
                let sid=PSID((&(*(ace as *const ACCESS_ALLOWED_ACE)).SidStart as *const u32).cast_mut().cast());
                assert!(IsWellKnownSid(sid,WinBuiltinAdministratorsSid).as_bool());
                assert_eq!(mask,0x80000000|0x20000000); // Generic read/execute, no write/delete/full grant.
                LocalFree(Some(HLOCAL(descriptor.0)));
            }
        }
        #[test]fn rejects_unsigned_component(){assert!(trust(&std::env::current_exe().unwrap()).is_err());}
        #[test]fn locked_file_denies_write_delete(){
            let p=std::env::temp_dir().join(format!("fil-lock-test-{}",std::process::id()));
            let mut w=OpenOptions::new().write(true).create_new(true).open(&p).unwrap();w.write_all(b"test").unwrap();drop(w);let f=lock(&p,false).unwrap();
            assert!(OpenOptions::new().write(true).open(&p).is_err());assert!(fs::remove_file(&p).is_err());drop(f);fs::remove_file(p).unwrap();
        }
    }
}
#[cfg(windows)] pub use windows_impl::{run,verify_embedded};
#[cfg(test)] mod tests {
 use super::*;
 #[test]fn windows_paths(){for path in ["../evil","/abs","C:/evil","a:stream","a/../b","a//b","CON.txt","a/NUL","x.","x ","a\\..\\b","\\\\server\\file"]{assert!(safe_path(path).is_err(),"{path}");}assert_eq!(safe_path(".\\data\\app.so").unwrap(),"data/app.so");}
 #[test]fn sha256_known_answer(){assert_eq!(hash(b"abc"),"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");}
 #[test]fn corrupt_brotli_fails(){let f=crate::bin_reader::BinaryData{path:"x".into(),raw:b"invalid",md5_code:b""};assert!(decode(&f,2,&hash(b"ok")).is_err());}
#[test]
fn readback_exact_empty_and_multibuffer() {
    for bytes in [vec![],vec![7;1],vec![91;100_003]] {
        assert!(verify_readback(&mut std::io::Cursor::new(&bytes),&bytes).is_ok());
    }
}
#[test]
fn readback_rejects_truncation_mutation_and_extension() {
    let expected=vec![71;100_003];
    for bytes in [expected[..100_002].to_vec(),{let mut b=expected.clone();b[65_536]=72;b},{let mut b=expected.clone();b.push(0);b}] {
        assert!(verify_readback(&mut std::io::Cursor::new(bytes),&expected).is_err());
    }
    assert!(verify_readback(&mut std::io::Cursor::new([0]),&[]).is_err());
}
#[test]
fn readback_rejects_reader_failure() {
    struct Broken;
    impl std::io::Read for Broken {fn read(&mut self,_:&mut[u8])->std::io::Result<usize>{Err(std::io::Error::new(std::io::ErrorKind::Other,"fixture"))}}
    assert!(verify_readback(&mut Broken,b"a").is_err());
    assert!(verify_readback(&mut Broken,b"").is_err());
}

}
