# SPDX-License-Identifier: MIT
"""Explicit trusted developer execution. Windows Job owns all descendants.

Reuses the existing profile owner's Job Object structures. The initial process
is suspended until assignment succeeds; no child can run before ownership.
This is process lifetime ownership, not filesystem/network confinement.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread, RLock
import time
from uuid import uuid4
from renulus.runtime.harness_profile_owner import _Kernel, _Accounting


class ShellOwnershipError(RuntimeError):
    pass


class TrustedShell:
    @staticmethod
    def start(argv, *, cwd, workspace, environment, current, mode, timeout_ms=30000, max_output_bytes=262144, pipes=False):
        # Arbitrary programs are never exposed to doctor, child or temporary sessions.
        if mode != "developer":
            raise ShellOwnershipError("shell_developer_mode_required")
        if (os.name != "nt" or not callable(current) or not isinstance(argv,list) or not argv
                or len(argv)>64 or any(not isinstance(v,str) or "\0" in v or len(v)>16000 for v in argv)
                or not Path(argv[0]).is_absolute() or not Path(argv[0]).is_file()
                or not 1<=timeout_ms<=60000 or not 1<=max_output_bytes<=1024*1024):
            raise ShellOwnershipError("shell_launch_invalid")
        root, target = Path(workspace), Path(cwd)
        if not root.is_absolute() or not target.is_absolute() or not target.is_relative_to(root):
            raise ShellOwnershipError("shell_workspace_denied")
        for part in [root,target,*target.parents]:
            if part.exists() and (part.is_symlink() or part.is_junction() or part.resolve()!=part):
                raise ShellOwnershipError("shell_workspace_alias")
            if part==root:
                break
        permitted={"SystemRoot","WINDIR","TEMP","TMP","PATH","PATHEXT","COMSPEC"}
        if (type(environment) is not dict or any(k not in permitted or not isinstance(v,str) or "\0" in v for k,v in environment.items())
                or not current()):
            raise ShellOwnershipError("shell_authority_stale")
        return OwnedShell(argv,target,environment,current,timeout_ms,max_output_bytes,pipes)


class OwnedShell:
    def __init__(self,argv,cwd,environment,current,timeout_ms,limit,pipes=False):
        # pipes: the caller owns bidirectional stdin/stdout (MCP stdio); stderr is discarded.
        self.kernel=_Kernel()
        self.job=self.kernel.job("Local\\RenulusDeveloperShell-"+uuid4().hex)
        self.kernel.api.TerminateJobObject.argtypes=[wintypes.HANDLE,wintypes.UINT]
        self.kernel.api.TerminateJobObject.restype=wintypes.BOOL
        self.current,self.deadline,self.limit=current,time.monotonic()+timeout_ms/1000,limit
        self.lock=RLock()
        self.output=bytearray()
        self.overflow=False
        self.closed=False
        self.process=None
        try:
            self.process=subprocess.Popen(argv,cwd=str(cwd),env=dict(environment),
                stdin=subprocess.PIPE if pipes else subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL if pipes else subprocess.STDOUT,shell=False,
                creationflags=0x00000004|subprocess.CREATE_NO_WINDOW,close_fds=True)  # CREATE_SUSPENDED
            handle=wintypes.HANDLE(int(self.process._handle))
            self.identity=self.kernel.identity(handle,self.process.pid)
            if not self.kernel.api.AssignProcessToJobObject(self.job,handle):
                raise ShellOwnershipError("shell_job_assignment_failed")
            self.kernel.require_member(handle,self.job)
            if not current():
                raise ShellOwnershipError("shell_authority_stale")
            resume=ctypes.WinDLL("ntdll").NtResumeProcess
            resume.argtypes=[wintypes.HANDLE]
            resume.restype=wintypes.LONG
            if resume(handle)!=0:
                raise ShellOwnershipError("shell_resume_failed")
            self.reader=None if pipes else Thread(target=self._read,name="renulus-owned-shell-output",daemon=True)
            if self.reader:
                self.reader.start()
        except BaseException:
            if self.process is not None:
                self.process.kill()
                self.process.wait(timeout=5)
            self.kernel.api.CloseHandle(self.job)
            self.job=None
            raise

    def _read(self):
        try:
            while True:
                data=self.process.stdout.read(4096)
                if not data:
                    return
                with self.lock:
                    available=max(0,self.limit-len(self.output))
                    self.output.extend(data[:available])
                    if len(data)>available:
                        self.overflow=True
                        self.kernel.api.TerminateJobObject(self.job,1)
        finally:
            self.process.stdout.close()

    def _active(self):
        accounting=_Accounting()
        if not self.kernel.api.QueryInformationJobObject(self.job,1,ctypes.byref(accounting),ctypes.sizeof(accounting),None):
            raise ShellOwnershipError("shell_descendants_uncertain")
        return accounting.active

    def terminate(self):
        with self.lock:
            if self.closed:
                return {"descendants_settled":True,"effects":"uncertain"}
            # Retain exact members before termination: job accounting reaching zero
            # can precede the final process handle becoming signalled on Windows.
            class Members(ctypes.Structure):
                _fields_=[('assigned',wintypes.DWORD),('count',wintypes.DWORD),('ids',ctypes.c_size_t*1024)]
            members=Members()
            if not self.kernel.api.QueryInformationJobObject(self.job,3,ctypes.byref(members),ctypes.sizeof(members),None) or members.count>1024:
                raise ShellOwnershipError('shell_descendants_uncertain')
            handles=[]
            for pid in members.ids[:members.count]:
                handle=self.kernel.api.OpenProcess(0x00100000,False,pid)
                if handle:handles.append(handle)
            if not self.kernel.api.TerminateJobObject(self.job,1):
                for handle in handles:self.kernel.api.CloseHandle(handle)
                raise ShellOwnershipError("shell_termination_uncertain")
        deadline=time.monotonic()+5
        while self._active():
            if time.monotonic()>=deadline:
                raise ShellOwnershipError("shell_descendants_uncertain")
            time.sleep(.01)
        self.process.wait(timeout=1)
        try:
            for handle in handles:
                if self.kernel.api.WaitForSingleObject(handle,5000)!=0:
                    raise ShellOwnershipError('shell_descendants_uncertain')
        finally:
            for handle in handles:self.kernel.api.CloseHandle(handle)
        if self.reader:
            self.reader.join(timeout=1)
        if self.reader and self.reader.is_alive():
            raise ShellOwnershipError("shell_output_unsettled")
        with self.lock:
            self.kernel.api.CloseHandle(self.job)
            self.job=None
            self.closed=True
        return {"descendants_settled":True,"effects":"uncertain"}

    def wait(self,cancel_event=None):
        cancel_event=cancel_event or Event()
        while self.process.poll() is None or self._active():
            if cancel_event.is_set() or not self.current() or time.monotonic()>=self.deadline or self.overflow:
                break
            time.sleep(.01)
        # A parent exiting does not settle a surviving child. Always join the Job.
        settlement=self.terminate()
        return {"exit_code":self.process.returncode,"output":bytes(self.output).decode("utf8",errors="replace"),
            **settlement,"pid":self.identity.pid,"creation_filetime":self.identity.creation_filetime}


def serve(stdin=None, stdout=None):
    """One owned shell per helper process, driven by the TypeScript developer plugin.

    stdin line 1 is the launch request; later lines are heartbeats proving the host
    still holds a current lease (`{"stop": true}` or 1s of silence revokes it).
    The single stdout line reports the settled result or the exact refusal.
    """
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    request = json.loads(stdin.readline())
    state = {"seen": time.monotonic(), "stop": False}

    def listen():
        try:
            for line in stdin:
                if json.loads(line).get("stop") is True:
                    break
                state["seen"] = time.monotonic()
        except (ValueError, OSError):
            pass
        state["stop"] = True

    Thread(target=listen, name="renulus-owned-shell-heartbeat", daemon=True).start()
    try:
        owned = TrustedShell.start(request["argv"], cwd=request["cwd"], workspace=request["workspace"],
            environment=request["environment"], mode=request["mode"], timeout_ms=request["timeout_ms"],
            max_output_bytes=request["max_output_bytes"],
            current=lambda: not state["stop"] and time.monotonic() - state["seen"] < 1.0)
        reply = {"ok": True, **owned.wait()}
    except ShellOwnershipError as error:
        reply = {"ok": False, "error": str(error), "descendants_settled": False, "effects": "uncertain"}
    stdout.write(json.dumps(reply) + "\n")
    stdout.flush()


if __name__ == "__main__":
    serve()
    os._exit(0)  # The heartbeat reader is a daemon thread blocked on stdin.
