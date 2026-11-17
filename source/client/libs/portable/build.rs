fn main() {
    println!("cargo:rerun-if-changed=fil_payload.rs");
    println!("cargo:rerun-if-changed=data.bin");
    if std::env::var("CARGO_CFG_TARGET_OS").unwrap_or_default()=="windows" {
        std::fs::copy("fil_payload.rs", std::path::Path::new(&std::env::var("OUT_DIR").unwrap()).join("fil_payload.rs")).expect("Generate authenticated payload inventory before Windows build");
    }
    if std::env::var("CARGO_CFG_TARGET_ENV").unwrap_or_default()=="msvc" {
        // Protect imports before main() can set DLL search policy (Windows10 RS1+).
        println!("cargo:rustc-link-arg=/DEPENDENTLOADFLAG:0x800");
    }
    #[cfg(windows)]
    {
        use std::io::Write;
        let mut res = winres::WindowsResource::new();
        res.set("CompanyName", "Fil Teknoloji")
            .set("ProductName", "FilDesk")
            .set("OriginalFilename", "FilDesk.exe")
            .set("InternalName", "FilDesk")
            .set("FileDescription", "FilDesk development build")
            .set("ProductVersion", "1.5.0+77")
            .set("FileVersion", "1.5.0.77")
            .set_version_info(winres::VersionInfo::PRODUCTVERSION, 0x0001_0005_0000_004d)
            .set_version_info(winres::VersionInfo::FILEVERSION, 0x0001_0005_0000_004d)
            .set_icon("../../res/icon.ico")
            .set_language(winapi::um::winnt::MAKELANGID(
                winapi::um::winnt::LANG_ENGLISH,
                winapi::um::winnt::SUBLANG_ENGLISH_US,
            ))
            .set_manifest_file("../../res/manifest.xml");
        match res.compile() {
            Err(e) => {
                write!(std::io::stderr(), "{}", e).unwrap();
                std::process::exit(1);
            }
            Ok(_) => {}
        }
    }
}
