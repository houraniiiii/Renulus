# SPDX-License-Identifier: MIT
import json
import os
from pathlib import Path
import socket
import sys
from io import StringIO
from tempfile import TemporaryDirectory
from unittest import mock
from threading import Event
import time
import unittest
from renulus.workers.capability_shell import OwnedShell, TrustedShell, serve


@unittest.skipUnless(os.name=="nt","Windows Job Object acceptance")
class TrustedShellTests(unittest.TestCase):
    def test_trusted_os_effects_and_surviving_descendant_are_owned_until_job_death(self):
        with TemporaryDirectory(prefix="renulus-capability-shell-") as folder:
            root=Path(folder)
            workspace=root/"workspace"
            workspace.mkdir()
            outside=root/"outside-workspace.txt"
            descendant=root/"descendant.json"
            server=socket.socket()
            server.bind(("127.0.0.1",0))
            server.listen()
            server.settimeout(5)
            script=root/"synthetic.py"
            child="import os,time,json;from pathlib import Path;Path("+repr(str(descendant))+").write_text(json.dumps({'pid':os.getpid()}));time.sleep(30)"
            script.write_text("import subprocess,socket;from pathlib import Path\nPath("+repr(str(outside))+").write_text('SYNTHETIC trusted effect')\n"
                +"socket.create_connection(('127.0.0.1',"+str(server.getsockname()[1])+"),timeout=2).close()\n"
                +"subprocess.Popen(["+repr(sys.executable)+",'-c',"+repr(child)+"])\n",encoding="utf8")
            env={k:os.environ[k] for k in ("SystemRoot","WINDIR","TEMP","TMP") if k in os.environ}
            owner=TrustedShell.start([sys.executable,str(script)],cwd=str(workspace),workspace=str(workspace),environment=env,current=lambda:True,mode="developer",timeout_ms=5000)
            try:
                peer,_=server.accept()
                peer.close()
                deadline=time.monotonic()+5
                while not descendant.exists() and time.monotonic()<deadline:
                    time.sleep(.01)
                self.assertEqual(outside.read_text(),"SYNTHETIC trusted effect")
                child_pid=json.loads(descendant.read_text())["pid"]
                self.assertGreater(owner._active(),0)
                cancellation=Event()
                cancellation.set()
                result=owner.wait(cancellation)
                self.assertTrue(result["descendants_settled"])
                self.assertEqual(result["effects"],"uncertain")
                process=owner.kernel.api.OpenProcess(0x00100000,False,child_pid)
                if process:
                    try:self.assertEqual(owner.kernel.api.WaitForSingleObject(process,0),0)
                    finally:owner.kernel.api.CloseHandle(process)
            finally:
                owner.terminate()
                server.close()

    def test_doctor_mode_is_refused_and_a_failed_job_query_is_reported_as_uncertain(self):
        class Heartbeats:
            def __init__(self,first):self.first=first
            def readline(self):return self.first
            def __iter__(self):
                while True:
                    time.sleep(.05)
                    yield "{}"
        class FailingQuery:
            def __init__(self,real):self.real=real
            def __getattr__(self,name):return (lambda *args:0) if name=="QueryInformationJobObject" else getattr(self.real,name)
        with TemporaryDirectory(prefix="renulus-capability-shell-") as folder:
            workspace=Path(folder)
            env={k:os.environ[k] for k in ("SystemRoot","WINDIR","TEMP","TMP") if k in os.environ}
            start=lambda code,mode="developer":TrustedShell.start([sys.executable,"-c",code],cwd=str(workspace),workspace=str(workspace),
                environment=env,current=lambda:True,mode=mode,timeout_ms=5000)
            with self.assertRaisesRegex(Exception,"shell_developer_mode_required"):
                start("pass",mode="doctor")
            owner=start("import time;time.sleep(30)")
            real=owner.kernel.api
            try:
                owner.kernel.api=FailingQuery(real)
                with self.assertRaisesRegex(Exception,"shell_descendants_uncertain"):
                    owner.terminate()
            finally:
                owner.kernel.api=real
                owner.terminate()
            original=OwnedShell.__init__
            def failing_init(self,*args,**kwargs):
                original(self,*args,**kwargs)
                self.kernel.api=FailingQuery(self.kernel.api)
            request={"argv":[sys.executable,"-c","pass"],"cwd":str(workspace),"workspace":str(workspace),"environment":env,
                "mode":"developer","timeout_ms":5000,"max_output_bytes":4096}
            out=StringIO()
            with mock.patch.object(OwnedShell,"__init__",failing_init):
                serve(Heartbeats(json.dumps(request)),out)
            reply=json.loads(out.getvalue())
            self.assertFalse(reply["ok"]);self.assertEqual(reply["error"],"shell_descendants_uncertain")
            self.assertFalse(reply["descendants_settled"])


if __name__=="__main__":unittest.main()
