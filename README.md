<div id="top"></div>

# WD MyPassport Linux unlocker

## Table of contents
<ol>
  <li><a href="#features">Features</a></li>
  <li><a href="#console-log-example">Console log example</a></li>
  <li><a href="#requirements">Requirements</a></li>
  <li><a href="#download-and-installation">Download and installation</a></li>
  <li><a href="#usage">Usage</a></li>
  <li><a href="#troubleshooting">Troubleshooting</a></li>
  <li><a href="#contributing">Contributing</a></li>
  <li><a href="#license">License</a></li>
</ol>

<!-- FEATURES -->
## Features

Western Digital "My Passport" drives come with hardware encryption. The official WD Security unlocker software is only available for Windows and macOS. Existing Linux workarounds often rely on heavy external dependencies or compiled tools (like `sg3-utils` or `sg_raw`).

This repository provides two lightweight, smart scripts:
* **`unlock_WD_external_drive.py`**: Automatically detects a locked WD drive, asks for your password securely, unlocks the hardware controller via native Linux `SG_IO` SCSI commands, actively waits for the kernel to expose the decrypted partitions, and offers an interactive prompt to mount them immediately (including a handy `/etc/fstab` helper).
* **`eject_WD_external_drive.py`**: Safely flushes the OS cache, unmounts partitions, sends a SCSI `STOP UNIT` command to spin down the mechanical drive (which clears the encryption key from the drive's RAM), and logically disconnects it from the OS so you can safely unplug it.

**Zero external dependencies:** Everything is written using Python 3 standard libraries and standard Linux core utilities (`lsblk`, `mount`, `blockdev`).

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- CONSOLE LOG EXAMPLE -->
## Console log example

```text
root@Jarvis:~# ./unlock_WD_external_drive.py
Searching for locked WD drives...

Locked drive found: /dev/sda
Password for /dev/sda: 
Unlock command sent. Waiting for drive to respond...
Success! Drive unlocked.
Refreshing partition table...
Waiting for partitions to appear....

Found 2 partition(s):
[0] /dev/sda1 (Size: 16M, Filesystem: unknown)
[1] /dev/sda2 (Size: 1.8T, Filesystem: ntfs)

Select partition index to mount [0-1] or Enter to skip: 1
Mount point (e.g., /mnt/wd_storage): /mnt/wd
Mounting /dev/sda2...
Mount successful!

============================================================
To auto-mount, add this to /etc/fstab (using UUID is recommended):
/dev/sda2  /mnt/wd  auto  defaults  0  0
============================================================
```

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- REQUIREMENTS -->
## Requirements

* **OS:** Any Linux distribution (Debian, Ubuntu, Proxmox, Arch, RHEL, etc.).
* **Python:** Python 3.x installed (usually pre-installed on most modern Linux distros).
* **Tools:** `lsblk`, `mount`, `blockdev` (provided by default via `util-linux` and `mount` packages).
* **Permissions:** Root privileges (required to send raw SCSI ioctl commands to `/dev/sdX`).

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- DOWNLOAD AND INSTALLATION -->
## Download and installation

Clone the repository and make the Python scripts executable:

```bash
git clone https://github.com/tigerblue77/WD_MyPassport_Linux_unlocker.git
cd WD_MyPassport_Linux_unlocker
chmod +x unlock_WD_external_drive.py eject_WD_external_drive.py
```

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- USAGE -->
## Usage

### 1. Unlock and mount a drive

Plug in your WD external drive, wait a few seconds for Linux to detect the USB device, and run:

```bash
sudo ./unlock_WD_external_drive.py
```
The script will handle the decryption and present you with an interactive menu to mount the discovered partitions. If the mount point directory doesn't exist, the script will automatically create it for you.

### 2. Lock and eject a drive

Because the WD decryption key remains in the drive's RAM as long as it receives 5V USB power, the only way to lock it again is to power it off. The `eject_WD_external_drive.py` script safely unmounts your partitions and sends a hardware spin-down command to wipe the RAM and lock the drive before you unplug it.

```bash
sudo ./eject_WD_external_drive.py
```

*(Note: If you want to remount the drive without physically unplugging the USB cable, you can force the Linux kernel to rescan USB ports by running: `for host in /sys/class/scsi_host/host*/scan; do echo "- - -" | sudo tee "$host" > /dev/null; done`)*

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- TROUBLESHOOTING -->
## Troubleshooting

### The script says "No locked WD drives found."
* **Reason 1:** You just plugged it in and the OS hasn't initialized the USB mass storage yet. Wait 5-10 seconds and try again.
* **Reason 2:** The drive is already unlocked. If the drive hasn't lost power (5V), it stays unlocked. Use `./eject_WD_external_drive.py` or physically unplug/replug the drive to lock it again.

### Mount failed: unknown filesystem or ReFS
Linux does not support Windows ReFS natively, and might lack drivers for exFAT if you are running a very old kernel. Make sure you install the necessary packages (e.g., `apt install exfat-fuse ntfs-3g`) if your drive uses those filesystems.

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- LICENSE -->
## License

Shield: [![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa]. The full license description can be read [here][link-to-license-file].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg
[link-to-license-file]: ./LICENSE

<p align="right">(<a href="#top">back to top</a>)</p>
