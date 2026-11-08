import re
from typing import Dict, Any, Tuple, List
from enum import Enum

class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

def _split_compound_commands(cmd: str) -> List[str]:
    """Splits shell command on top-level ';' or '&&' outside quotes."""
    segments: List[str] = []
    cur: List[str] = []
    in_quote = None
    i = 0
    n = len(cmd)
    while i < n:
        ch = cmd[i]
        if ch in ('"', "'") and (i == 0 or cmd[i - 1] != "\\"):
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
            cur.append(ch)
        elif in_quote is None and ch == ";":
            seg = "".join(cur).strip()
            if seg:
                segments.append(seg)
            cur = []
        elif in_quote is None and ch == "&" and i + 1 < n and cmd[i + 1] == "&":
            seg = "".join(cur).strip()
            if seg:
                segments.append(seg)
            cur = []
            i += 1
        else:
            cur.append(ch)
        i += 1
    seg = "".join(cur).strip()
    if seg:
        segments.append(seg)
    return segments

class RiskEngine:
    # Highly destructive patterns that are strictly CRITICAL
    CRITICAL_PATTERNS = [
        r"(?i)\bformat\b\s+[a-z]:",
        r"(?i)\bdiskpart\b",
        r"(?i)\bbootrec\b",
        r"(?i)\bbcdedit\b",
        r"(?i)rmdir\s+/[sS]\s+/[qQ]\s+[c-zC-Z]:\\?$",
        r"(?i)del\s+/[sS]\s+/[qQ]\s+[c-zC-Z]:\\?$",
        r"(?i)Remove-Item\s+.*-Recurse\s+.*[c-zC-Z]:\\?$",
        r"(?i)Remove-Item\s+.*-Recurse\s+.*C:\\Windows",
        r"(?i)\bSet-MpPreference\s+-DisableRealtimeMonitoring\s+\$true\b",
        r"(?i)\bnetsh\s+advfirewall\s+set\s+allprofiles\s+state\s+off\b",
        r"(?i)reg\s+delete\s+HKLM",
        r"(?i)\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/(?:\s|$|\*)",
    ]

    # Sensitive/mutating commands that are HIGH risk
    HIGH_PATTERNS = [
        r"(?i)(?:^|[\s;&|])del\s+[^\s]",
        r"(?i)\brmdir\b",
        r"(?i)\bRemove-Item\b",
        r"(?i)\bStop-Process\b",
        r"(?i)\btaskkill\b",
        r"(?i)\bnetsh\b",
        r"(?i)\breg\s+(add|delete)\b",
        r"(?i)\bSet-ExecutionPolicy\b",
        r"(?i)\bNew-Service\b",
        r"(?i)\bsc\s+(create|delete|config)\b",
        r"(?i)\bshutdown\b",
        r"(?i)\brestart-computer\b",
        r"(?i)icacls\b",
        r"(?i)takeown\b",
    ]

    # Safe low-risk, read-only diagnostic commands
    LOW_PATTERNS = [
        r"(?i)^(\s*Get-ChildItem|\s*dir|\s*ls|\s*gci)\b",
        r"(?i)^(\s*Get-Location|\s*pwd|\s*cd|\s*Set-Location|\s*chdir|\s*pushd|\s*popd)\b",
        r"(?i)^(\s*Get-Process|\s*ps)\b",
        r"(?i)^(\s*Get-Service)\b",
        r"(?i)^(\s*Get-Date)\b",
        r"(?i)^(\s*Get-Content|\s*cat|\s*type|\s*head|\s*tail|\s*grep|\s*find|\s*wc|\s*stat|\s*file)\b",
        r"(?i)^(\s*systeminfo|\s*uname|\s*df|\s*free)\b",
        r"(?i)^(\s*ipconfig|\s*ifconfig|\s*ip\s+addr)\b",
        r"(?i)^(\s*hostname)\b",
        r"(?i)^(\s*whoami|\s*id)\b",
        r"(?i)^(\s*curl(\.exe)?)\b",
        r"(?i)^(\s*\(?Invoke-WebRequest|\s*\(?iwr|\s*\(?Invoke-RestMethod|\s*\(?irm)\b",
        r"(?i)^(\s*ping|\s*tracert|\s*traceroute|\s*nslookup|\s*netstat)\b",
        r"(?i)^(\s*Get-NetIPAddress|\s*Test-NetConnection|\s*Resolve-DnsName)\b",
        r"(?i)^(\s*echo|\s*Write-Output|\s*Write-Host)\b",
        r"(?i)^(\s*where(\.exe)?|\s*which|\s*Get-Command)\b",
        r"(?i)^(\s*git\s+(status|log|branch|diff|remote))\b",
        r"(?i)^(\s*python3?\s+--version|\s*node\s+-v|\s*npm\s+-v)\b",
        r"(?i)^(\s*Get-CimInstance|\s*Get-WmiObject|\s*wmic)\b",
        r"(?i)^(\s*nvidia-smi|\s*dxdiag)\b",
        r"(?i)^(\s*Get-ItemProperty|\s*Get-Item|\s*Test-Path|\s*Get-FileHash)\b",
        r"(?i)^(\s*Get-Volume|\s*Get-Partition|\s*Get-Disk)\b",
        r"(?i)^(\s*Get-ComputerInfo|\s*Get-CimClass)\b",
        r"(?i)^(\s*Add-Type)\b",
        r"(?i)^(\s*\[System\.)",
        r"(?i)^(\s*\$[a-zA-Z0-9_]+\s*=)",
    ]

    _DANGEROUS_PIPE_OR_WRITE_RE = re.compile(
        r"(?i)(\|\s*(Remove-Item|del|Stop-Process|taskkill|Out-File|Set-Content|Add-Content|rm\b)|"
        r"(?:^|[^-])>\s*[^\s&]|>>\s*[^\s])"
    )

    @classmethod
    def _is_segment_low_risk(cls, segment: str) -> bool:
        if cls._DANGEROUS_PIPE_OR_WRITE_RE.search(segment):
            return False
        for pattern in cls.LOW_PATTERNS:
            if re.search(pattern, segment):
                return True
        return False

    @classmethod
    def classify_command(cls, command: str, shell: str = "powershell") -> Tuple[RiskLevel, str]:
        cmd_clean = command.strip()
        if not cmd_clean:
            return RiskLevel.LOW, "Empty command"

        # Core NOVA self-modification attempts are always CRITICAL
        from backend.app.core.security import command_targets_nova_core_mutation
        is_core_mod, _ = command_targets_nova_core_mutation(cmd_clean)
        if is_core_mod:
            return RiskLevel.CRITICAL, "Operation attempts to modify protected NOVA core files"

        # Check CRITICAL
        for pattern in cls.CRITICAL_PATTERNS:
            if re.search(pattern, cmd_clean):
                return RiskLevel.CRITICAL, "Operation matches critical destructive system pattern"

        # Check HIGH
        for pattern in cls.HIGH_PATTERNS:
            if re.search(pattern, cmd_clean):
                return RiskLevel.HIGH, "Operation modifies or deletes processes, services, or registry"

        # Check LOW across all top-level compound segments (e.g. "cd path; Get-ChildItem ...")
        segments = _split_compound_commands(cmd_clean)
        if segments and all(cls._is_segment_low_risk(seg) for seg in segments):
            return RiskLevel.LOW, "Safe read-only inspection command"

        # Default fallback for arbitrary scripts/commands
        return RiskLevel.MODERATE, "Standard operational command requiring evaluation"
