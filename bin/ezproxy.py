#!/usr/bin/env python3

# https://www.xmodulo.com/change-system-proxy-settings-command-line-ubuntu-desktop.html
from time import sleep
import signal
from subprocess import run, Popen

proc = None

terminate = False


def handle_exit(signum, frame):
    global terminate
    terminate = True


signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGHUP, handle_exit)


def run_ssh_process():
    global proc
    global terminate
    res = run("/usr/bin/ssh-add -l".split(" "), capture_output=True)
    print(res)
    key_added = False
    for line in res.stdout.decode('UTF-8').split('\n'):
        parts = line.split(" ")
        # print(parts)
        if len(parts) == 0:
            continue
        if '/home/pgk/.ssh/main_rsa' == parts[2]:
            key_added = True
            break

    if not key_added:
        run("/usr/bin/ssh-add /home/pgk/.ssh/main_rsa".split(" "))

    run("gsettings set org.gnome.system.proxy mode 'auto'".split(" "))
    run("gsettings set org.gnome.system.proxy autoconfig-url https://pac.a8c.com/".split(" "))
    while not terminate:
        if proc is None:
            proc = Popen(['/usr/bin/ssh', '-N', '-D', '8080', '-i',
                          '/home/pgk/.ssh/main_rsa',
                          'panoskountanis@proxy.automattic.com'])
        rc = proc.poll()
        if rc is not None:
            proc = None
        sleep(1)
    run("gsettings set org.gnome.system.proxy mode 'none'".split(" "))


if __name__ == "__main__":
    run_ssh_process()
    # try:
    #     from tkinter import *
    #     from tkinter import ttk
    # except ImportError as e:
    #     print('you need to install python3 tcl/tk support for this to run')
    #     exit(1)

    # root = Tk()
    # frm = ttk.Frame(root, padding=10)
    # frm.grid()
    # ttk.Label(frm, text="Ezproxy for linux").grid(column=0, row=0)
    # ttk.Button(frm, text="Start", command=root.destroy).grid(column=1, row=1)
    # ttk.Button(frm, text="Stop", command=root.destroy).grid(column=2, row=1)
    # root.mainloop()
