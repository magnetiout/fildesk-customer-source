#include <windows.h>
#include <cassert>
#include "../client/flutter/windows/runner/fildesk_identity.h"
int main() {
  const wchar_t* identities[] = {L"FilDesk", L"FilDesk-Dev", L"FilDesk-Operator", L"FilDesk-Dev-Operator"};
  HWND windows[4] = {};
  for (int i=0; i<4; ++i) {
    const auto name = FilDeskWindowClass(identities[i]);
    const auto title = FilDeskWindowTitle(identities[i]);
    assert(title == (i<2 ? L"FilDesk" : L"FilDesk Operator"));
    WNDCLASSW cls{};
    cls.lpfnWndProc=DefWindowProcW;
    cls.hInstance=GetModuleHandleW(nullptr);
    cls.lpszClassName=name.c_str();
    assert(RegisterClassW(&cls));
    windows[i]=CreateWindowW(name.c_str(),title.c_str(),WS_OVERLAPPEDWINDOW,
      0,0,100,100,nullptr,nullptr,cls.hInstance,nullptr);
    assert(windows[i]);
  }
  for (int i=0; i<4; ++i) {
    assert(FilDeskWindowClass(identities[i]) != L"FLUTTER_RUNNER_WIN32_WINDOW_" + std::wstring(identities[i]));
    ShowWindow(windows[i], SW_MINIMIZE);
    SetWindowPos(windows[i], nullptr, 32000, 32000, 100, 100, SWP_NOZORDER|SWP_NOACTIVATE);
    FilRestoreVisible(windows[i]);
    assert(!IsIconic(windows[i]));
    assert(MonitorFromWindow(windows[i], MONITOR_DEFAULTTONULL) != nullptr);
    assert(FindWindowW(FilDeskWindowClass(identities[i]).c_str(),
      FilDeskWindowTitle(identities[i]).c_str()) == windows[i]);
    for (int j=0; j<i; ++j) assert(windows[i] != windows[j]);
    DestroyWindow(windows[i]);
    UnregisterClassW(FilDeskWindowClass(identities[i]).c_str(),GetModuleHandleW(nullptr));
  }
}
