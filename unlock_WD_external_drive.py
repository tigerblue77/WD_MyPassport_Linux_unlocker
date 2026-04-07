#!/usr/bin/env python3

import os
import sys
import fcntl
import ctypes
import hashlib
import getpass
import time
import glob
import subprocess

# Constants for SCSI communication with the kernel (SG_IO ioctl)
SG_IO = 0x2285
SG_DXFER_NONE = -1
SG_DXFER_TO_DEV = -2
SG_DXFER_FROM_DEV = -3

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

def send_scsi_cmd(fd, cdb, data_dir, data_buf, dxfer_len):
    cmdp = ctypes.create_string_buffer(cdb, len(cdb))
    sbp = ctypes.create_string_buffer(32)
    
    hdr = sg_io_hdr()
    hdr.interface_id = ord('S')
    hdr.dxfer_direction = data_dir
    hdr.cmd_len = len(cdb)
    hdr.mx_sb_len = 32
    hdr.iovec_count = 0
    hdr.dxfer_len = dxfer_len
    hdr.dxferp = ctypes.cast(data_buf, ctypes.c_void_p) if data_buf else None
    hdr.cmdp = ctypes.cast(cmdp, ctypes.c_void_p)
    hdr.sbp = ctypes.cast(sbp, ctypes.c_void_p)
    hdr.timeout = 5000
    hdr.flags = 0
    
    try:
        fcntl.ioctl(fd, SG_IO, hdr)
        return hdr.status == 0
    except OSError:
        return False

def check_wd_status(fd):
    cdb = bytes.fromhex("c0 45 00 00 00 00 00 00 30 00")
    data_buf = ctypes.create_string_buffer(32)
    
    if send_scsi_cmd(fd, cdb, SG_DXFER_FROM_DEV, data_buf, 32):
        result = bytes(data_buf)
        if result.startswith(bytes.fromhex("45000001")):
            return "locked"
        elif result.startswith(bytes.fromhex("45000002")):
            return "unlocked"
    return "unknown"

def unlock_wd(fd, password):
    passwd = "WDC." + password
    passwd_bytes = passwd.encode("utf-16")[2:]
    for _ in range(1000):
        passwd_bytes = hashlib.sha256(passwd_bytes).digest()
    
    header = bytes.fromhex("4500000000000020")
    payload = header + passwd_bytes
    
    cdb = bytes.fromhex("c1 e1 00 00 00 00 00 00 28 00")
    data_buf = ctypes.create_string_buffer(payload, len(payload))
    
    return send_scsi_cmd(fd, cdb, SG_DXFER_TO_DEV, data_buf, len(payload))

def main():
    if os.geteuid() != 0:
        print("Error: This script must be run as root (e.g., sudo ./unlock_wd.py).")
        sys.exit(1)

    print("Searching for locked WD drives...")
    locked_devices = []

    for dev_path in glob.glob('/dev/sd[a-z]'):
        try:
            fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
            status = check_wd_status(fd)
            os.close(fd)
            
            if status == "locked":
                locked_devices.append(dev_path)
        except OSError:
            continue

    if not locked_devices:
        print("No locked WD drives were found.")
        sys.exit(1)

    for dev in locked_devices:
        print(f"\nLocked drive found at: {dev}")
        password = getpass.getpass(f"Enter password for {dev}: ")
        
        try:
            fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
            print("Attempting to unlock...")
            unlock_wd(fd, password)
            time.sleep(1)
            
            status_after = check_wd_status(fd)
            os.close(fd)
            
            if status_after == "unlocked":
                print("Success! The drive has been unlocked.")
                print("Refreshing partition table via blockdev...")
                
                try:
                    subprocess.run(["blockdev", "--rereadpt", dev], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(0.5)
                    print("Done! Your partitions are now ready (use lsblk or mount).")
                except subprocess.CalledProcessError:
                    print(f"Unlock successful, but automatic refresh failed. Run: blockdev --rereadpt {dev}")
            else:
                print("Unlock failed. Incorrect password?")
                
        except OSError as e:
            print(f"Error accessing device {dev}: {e}")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Operation cancelled by user.")
        sys.exit(130)
