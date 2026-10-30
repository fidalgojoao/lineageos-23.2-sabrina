"""Offer Install anyway? for unverified packages while the menu is visible, on this user build."""
from pathlib import Path
p=Path('/opt/sabrina/android16/bootable/recovery/recovery.cpp');t=p.read_text()
old='''bool ask_to_continue_unverified(Device* device) {
  if (get_build_type() == "user") {
    return false;
  } else {
    device->GetUI()->SetProgressType(RecoveryUI::EMPTY);
    return yes_no(device, "Signature verification failed", "Install anyway?");
  }
}
'''
new='''bool ask_to_continue_unverified(Device* device) {
  // The caller only asks while the menu is visible, so automatic installs are still refused.
  device->GetUI()->SetProgressType(RecoveryUI::EMPTY);
  return yes_no(device, "Signature verification failed", "Install anyway?");
}
'''
if new in t:print('already patched');raise SystemExit
assert t.count(old)==1
p.write_text(t.replace(old,new));print('patched')
i=Path('/opt/sabrina/android16/bootable/recovery/install/install.cpp').read_text()
assert 'if (!ui->IsTextVisible() || !ask_to_continue_unverified(ui->GetDevice())) {' in i
print('hidden menu still refuses')
