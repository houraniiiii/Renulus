# SPDX-License-Identifier: MIT
import json
import os
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from threading import Event
import time
import unittest
from renulus.workers.capability_shell import TrustedShell


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


if __name__=="__main__":unittest.main()
