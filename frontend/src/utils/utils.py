import subprocess
import os
import re

from typing import List

from utils.logger import Logger

def log_trace(func):
    def wrap(*args, **kwargs):

        if args:
            if isinstance(args[0], str):
                cmd = re.sub(' +', ' ', args[0])
            elif isinstance(args[0], list):
                cmd = re.sub(' +', ' ', " ".join(args[0]))
        
            if kwargs.get("log_debug"):
                Logger.debug("Running command: " + cmd)
            else:
                Logger.info("Running command: " + cmd)

        return func(*args, **kwargs)
    
    return wrap

@log_trace
def invoke_subprocess(command: List[str] | str, capture_output: bool = True,
                      shell: bool = True, sudo: bool = False, 
                      dryrun: bool = False, log_debug: bool = False) -> subprocess.CompletedProcess:
    if dryrun:
        return subprocess.CompletedProcess("", returncode=0)

    sudo = False if os.geteuid() == 0 else sudo

    if isinstance(command, str) and sudo:
        command = "sudo " + command
    elif isinstance(command, list) and sudo:
        command = ["sudo"] + command

    return subprocess.run(command, capture_output=capture_output, shell=shell)

def run_fail_on_error(command: List[str] | str, shell: bool = True, 
                      sudo: bool = False, dryrun: bool = False, log_debug: bool = False) -> None:
    
    proc = invoke_subprocess(command, capture_output=True, shell=shell, 
                             sudo=sudo, dryrun=dryrun, log_debug=log_debug)

    if proc.returncode != 0:
        raise Exception(f"Command failed: {proc.stderr.decode("utf-8")}")

def run_log_on_error(command: List[str] | str, shell: bool = True,
                          sudo: bool = False, dryrun: bool = False, log_debug: bool = False) -> None:
    try:
        proc = invoke_subprocess(command, capture_output=True, shell=shell, sudo=sudo,
                                dryrun=dryrun, log_debug=log_debug)
    except Exception as ex:
        Logger.error(f"Unable to execute command: {ex}")
        return
    
    if proc.returncode != 0:
        msg = f"Command finished with error code {proc.returncode}, but error is ignored: {proc.stderr.decode('utf-8').replace('\n', '')}"
        if log_debug:
            Logger.debug(msg)
        else:
            Logger.warning(msg)
