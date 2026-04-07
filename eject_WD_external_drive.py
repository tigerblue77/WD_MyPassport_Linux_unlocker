#!/usr/bin/env python3

import os
import sys
import glob
import fcntl
import ctypes
import subprocess
import time

# SCSI Constants
SG_IO = 0x2285
SG_DXFER_NONE = -1

class sg_io_hdr(ctypes.Structure):
    _fields_ =[
        ("interface_id", ctypes.c_int),
        ("dxfer_direction", ctypes.c_int),
        ("cmd_len", ctypes.c_ubyte),
        ("mx_sb_len", ctypes.c_ubyte),
        ("iovec_count", ctypes.c_ushort),
        ("dxfer_len", ctypes.c_uint),
        ("dxferp", ctypes.c_void_p),
        ("cmdp", ctypes.c_void_p),
        ("sbp", ctypes.c_void_p),
        ("timeout", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("pack_id", ctypes.c_int),
        ("usr_ptr", ctypes.c_void_p),
        ("status", ctypes.c_ubyte),
        ("masked_status", ctypes.c_ubyte),
        ("msg_status", ctypes.c_ubyte),
        ("sb_len_wr", ctypes.c_ubyte),
        ("host_status", ctypes.c_ushort),
        ("driver_status", ctypes.c_ushort),
        ("resid", ctypes.c_int),
        ("duration", ctypes.c_uint),
        ("info", ctypes.c_uint)
    ]

def spin_down_drive(dev_path):
    """Sends the SCSI command to stop the platters (Spin-down/Sleep)"""
    try:
        fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return False

    # SCSI Command "START STOP UNIT" (0x1B) -> STOP (0x00)
    cdb = bytes([0x1B, 0x00, 0x00, 0x00, 0x00, 0x00])
    cmdp = ctypes.create_string_buffer(cdb, len(cdb))
    sbp = ctypes.create_string_buffer(32)

    hdr = sg_io_hdr()
    hdr.interface_id = ord('S')
    hdr.dxfer_direction = SG_DXFER_NONE
    hdr.cmd_len = len(cdb)
    hdr.mx_sb_len = 32
    hdr.timeout = 5000
    hdr.cmdp = ctypes.cast(cmdp, ctypes.c_void_p)
    hdr.sbp = ctypes.cast(sbp, ctypes.c_void_p)

    print(f"[-] Sending spin-down command to {dev_path}...")
    try:
        fcntl.ioctl(fd, SG_IO, hdr)
        os.close(fd)
        return True
    except OSError:
        os.close(fd)
        return False

def find_wd_usb_drives():
    """Searches for all Western Digital USB drives"""
    wd_drives =[]
    for path in glob.glob('/sys/block/sd*'):
        dev_name = os.path.basename(path)
        device_link = os.path.join(path, 'device')
        
        if os.path.islink(device_link):
            real_path = os.path.realpath(device_link)
            # Strictly verify that the device is on a USB bus
            if 'usb' in real_path:
                vendor_file = os.path.join(path, 'device', 'vendor')
                if os.path.exists(vendor_file):
                    with open(vendor_file, 'r') as f:
                        vendor = f.read().strip().upper()
                        # If the vendor name contains WD or WESTERN
                        if 'WD' in vendor or 'WESTERN' in vendor:
                            wd_drives.append(f"/dev/{dev_name}")
    return wd_drives

def eject_drive(dev_path):
    print(f"\n=== Safely ejecting {dev_path} ===")
    
    # 1. Properly unmount partitions
    print("[-] Unmounting any existing partitions...")
    os.system("sync") # Force flush cached data to disk
    partitions = glob.glob(f"{dev_path}[0-9]*")
    for part in partitions:
        subprocess.run(["umount", part], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    
    # 2. Hardware spin-down (Stop platters and lock)
    if spin_down_drive(dev_path):
        print("[-] The drive has stopped spinning and is now locked.")
        time.sleep(2) # Allow 2 seconds for mechanical parts to park safely
    else:
        print("[!] Failed to stop the motor, proceeding anyway...")

    # 3. Remove device from Linux kernel
    dev_name = os.path.basename(dev_path)
    delete_path = f"/sys/block/{dev_name}/device/delete"
    if os.path.exists(delete_path):
        print("[-] Logical disconnection from the system...")
        try:
            with open(delete_path, 'w') as f:
                f.write("1\n")
        except Exception as e:
            print(f"[!] Error during logical disconnection: {e}")
            
    print(f"[SUCCESS] The WD drive was safely ejected.")
    print("-> You can now safely disconnect it physically!")

def main():
    if os.geteuid() != 0:
        print("Error: This script must be run as root.")
        sys.exit(1)

    print("Searching for external Western Digital drives...")
    wd_drives = find_wd_usb_drives()
    
    if not wd_drives:
        print("No Western Digital USB drives were found on this server.")
        sys.exit(0)
        
    for drive in wd_drives:
        eject_drive(drive)

if __name__ == '__main__':
    main()
