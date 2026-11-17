#pragma once
#include <windows.h>
inline void FilMarkStartup(unsigned int phase) {
  const auto module = GetModuleHandleW(L"librustdesk.dll");
  if (!module) return;
  const auto mark = reinterpret_cast<void (*)(unsigned int)>(GetProcAddress(module, "fil_startup_phase"));
  if (mark) mark(phase);
}
