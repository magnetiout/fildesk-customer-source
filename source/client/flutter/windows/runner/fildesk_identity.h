#pragma once
#include <string>
#ifdef _WIN32
#include <windows.h>
#endif
#include <algorithm>

// Display branding must not merge separate profile/configuration namespaces.
inline std::wstring FilDeskWindowClass(const std::wstring& identity) {
  return L"FLUTTER_RUNNER_WIN32_WINDOW_" + identity + L"_1.5.0.77";
}
inline std::wstring FilDeskWindowTitle(const std::wstring& identity) {
  return identity.size() >= 9 && identity.substr(identity.size() - 9) == L"-Operator"
      ? L"FilDesk Operator" : L"FilDesk";
}

#ifdef _WIN32
// Explicit repeated launch only; restore onto a currently available work area.
inline void FilRestoreVisible(HWND hwnd) {
  ShowWindow(hwnd, SW_RESTORE);
  RECT rect; MONITORINFO monitor = {}; monitor.cbSize = sizeof(monitor);
  if (GetWindowRect(hwnd, &rect) && GetMonitorInfoW(MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), &monitor)) {
    const RECT work = monitor.rcWork;
    const int width = (std::min)(rect.right-rect.left, work.right-work.left);
    const int height = (std::min)(rect.bottom-rect.top, work.bottom-work.top);
    const int x = (std::max)(work.left, (std::min)(rect.left, work.right-width));
    const int y = (std::max)(work.top, (std::min)(rect.top, work.bottom-height));
    SetWindowPos(hwnd, nullptr, x, y, width, height, SWP_NOZORDER|SWP_NOACTIVATE);
  }
  if (!SetForegroundWindow(hwnd)) {
    FLASHWINFO flash = {sizeof(FLASHWINFO), hwnd, FLASHW_TRAY, 3, 0};
    FlashWindowEx(&flash);
  }
}

#endif
