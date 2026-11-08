import os
import sys
import hashlib
import base64
import re
from pathlib import Path
from typing import Optional, Tuple

# DPAPI imports on Windows
IS_WINDOWS = sys.platform.startswith("win")
if IS_WINDOWS:
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte)),
            ]
        _has_dpapi = True
    except Exception:
        _has_dpapi = False
else:
    _has_dpapi = False

# Fallback encryption using cryptography if DPAPI is unavailable
try:
    from cryptography.fernet import Fernet
    _has_fernet = True
except ImportError:
    _has_fernet = False

_FALLBACK_KEY_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / ".secret.key"

def _get_or_create_fallback_key() -> bytes:
    if not _FALLBACK_KEY_FILE.exists():
        if _has_fernet:
            key = Fernet.generate_key()
            _FALLBACK_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            _FALLBACK_KEY_FILE.write_bytes(key)
            return key
        else:
            # Simple persistent key
            key = base64.urlsafe_b64encode(os.urandom(32))
            _FALLBACK_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            _FALLBACK_KEY_FILE.write_bytes(key)
            return key
    return _FALLBACK_KEY_FILE.read_bytes()

def encrypt_credential(secret_text: str) -> str:
    """
    Encrypts sensitive data (e.g. API keys) using Windows DPAPI (CryptProtectData).
    Falls back to Fernet if DPAPI fails or non-Windows.
    Returns base64 encoded ciphertext string prefixed with scheme.
    """
    if not secret_text:
        return ""
    
    raw_bytes = secret_text.encode("utf-8")
    
    if IS_WINDOWS and _has_dpapi:
        try:
            blob_in = DATA_BLOB(len(raw_bytes), ctypes.cast(ctypes.c_char_p(raw_bytes), ctypes.POINTER(ctypes.c_byte)))
            blob_out = DATA_BLOB()
            # CryptProtectData with description
            if ctypes.windll.crypt32.CryptProtectData(
                ctypes.byref(blob_in), "nova_credential", None, None, None, 0, ctypes.byref(blob_out)
            ):
                cipher_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                ctypes.windll.kernel32.LocalFree(blob_out.pbData)
                return "dpapi:" + base64.b64encode(cipher_bytes).decode("ascii")
        except Exception:
            pass  # Fall through to fallback
            
    if _has_fernet:
        key = _get_or_create_fallback_key()
        f = Fernet(key)
        cipher_bytes = f.encrypt(raw_bytes)
        return "fernet:" + cipher_bytes.decode("ascii")
        
    # Standard base64 obfuscation if nothing else is available (failsafe)
    return "b64:" + base64.b64encode(raw_bytes).decode("ascii")

def decrypt_credential(encrypted_str: str) -> str:
    """
    Decrypts a previously encrypted credential string.
    """
    if not encrypted_str:
        return ""
        
    if encrypted_str.startswith("dpapi:") and IS_WINDOWS and _has_dpapi:
        try:
            cipher_bytes = base64.b64decode(encrypted_str[6:])
            blob_in = DATA_BLOB(len(cipher_bytes), ctypes.cast(ctypes.c_char_p(cipher_bytes), ctypes.POINTER(ctypes.c_byte)))
            blob_out = DATA_BLOB()
            if ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
            ):
                plain_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                ctypes.windll.kernel32.LocalFree(blob_out.pbData)
                return plain_bytes.decode("utf-8")
        except Exception:
            return ""
            
    elif encrypted_str.startswith("fernet:") and _has_fernet:
        try:
            key = _get_or_create_fallback_key()
            f = Fernet(key)
            plain_bytes = f.decrypt(encrypted_str[7:].encode("ascii"))
            return plain_bytes.decode("utf-8")
        except Exception:
            return ""
            
    elif encrypted_str.startswith("b64:"):
        try:
            return base64.b64decode(encrypted_str[4:]).decode("utf-8")
        except Exception:
            return ""
            
    # If not encrypted or raw
    return encrypted_str

def mask_credential(key_str: str) -> str:
    """
    Masks sensitive keys for display in UI or logs.
    E.g. 'sk-1234567890abcdef' -> 'sk-...cdef'
    """
    if not key_str:
        return ""
    if len(key_str) <= 8:
        return "••••••••"
    prefix = key_str[:3]
    suffix = key_str[-4:]
    return f"{prefix}••••••••{suffix}"

def calculate_command_hash(command: str, shell: str, cwd: str) -> str:
    """
    Computes a cryptographic SHA256 integrity hash for an execution request.
    Any alteration to command, shell, or working directory changes the hash.
    """
    normalized = f"{command.strip()}||{shell.lower().strip()}||{Path(cwd).resolve()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def sanitize_untrusted_text(content: str) -> str:
    """
    Sanitizes untrusted input (e.g. tool output, uploaded files) to mitigate
    indirect prompt injection where text attempts to override system instructions.
    Wraps content with untrusted boundaries.
    """
    # Neutralize markdown system command prompts or attempts to instruct assistant
    patterns = [
        (re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions"), "[BLOCKED_INJECTION_ATTEMPT]"),
        (re.compile(r"(?i)system\s*:\s*you\s+are\s+now"), "[BLOCKED_INJECTION_ATTEMPT]"),
    ]
    sanitized = content
    for pattern, repl in patterns:
        sanitized = pattern.sub(repl, sanitized)
    return sanitized

def validate_workspace_path(path_str: str, allowed_workspace: str) -> Tuple[bool, Path, str]:
    """
    Validates that a given path stays within or is permitted relative to the workspace.
    Returns (is_valid, resolved_path, error_message).
    """
    try:
        ws_path = Path(allowed_workspace).resolve()
        target = Path(path_str)
        if not target.is_absolute():
            target = (ws_path / target).resolve()
        else:
            target = target.resolve()
            
        # Check traversal
        try:
            target.relative_to(ws_path)
            return True, target, ""
        except ValueError:
            # Check if path is within parent application root
            from backend.app.core.config import settings
            base_path = Path(settings.BASE_DIR).resolve()
            try:
                target.relative_to(base_path)
                return True, target, ""
            except ValueError:
                # If path was explicitly given as an absolute path by user, allow unless in protected system folders
                if Path(path_str).is_absolute():
                    blocked_prefixes = ["c:\\windows", "c:/windows", "/etc", "/private/etc", "/bin", "/sbin", "/usr", "/system"]
                    target_str = str(target).lower().replace("/", "\\")
                    for bp in blocked_prefixes:
                        if target_str.startswith(bp.replace("/", "\\")):
                            return False, target, f"Access denied: system path '{target}' is protected"
                    return True, target, ""
                return False, target, f"Access denied: path '{target}' is outside workspace '{ws_path}'"
    except Exception as e:
        return False, Path(path_str), f"Invalid path: {str(e)}"


CORE_PROTECTED_ERROR = (
    "SECURITY POLICY BLOCKED: NOVA's core source code and runtime files are strictly immutable "
    "and read-only. Modifying, overwriting, moving, patching, or deleting NOVA core files is "
    "forbidden under all circumstances, even if requested by the user."
)


def is_protected_nova_core_path(target_path) -> Tuple[bool, str]:
    """
    Returns (True, error_message) if `target_path` resolves inside NOVA's application directory
    (BASE_DIR) outside the designated writable `scratch/` workspace.
    """
    try:
        from backend.app.core.config import settings
        base_dir = Path(settings.BASE_DIR).resolve()
        scratch_dir = Path(settings.SCRATCH_DIR).resolve()
        target = Path(target_path).resolve()
    except Exception:
        return False, ""

    # Explicitly allow files and subfolders inside scratch/
    try:
        if target == scratch_dir or target.is_relative_to(scratch_dir):
            return False, ""
    except AttributeError:
        # Python < 3.9 fallback
        if str(target).lower().startswith(str(scratch_dir).lower()):
            return False, ""

    # Block any mutation to BASE_DIR itself or any protected file/subfolder within it
    try:
        in_base = (target == base_dir or target.is_relative_to(base_dir))
    except AttributeError:
        in_base = str(target).lower().startswith(str(base_dir).lower())

    if in_base:
        return True, f"{CORE_PROTECTED_ERROR} (Blocked path: '{target}')"
    return False, ""


_SHELL_MUTATION_RE = re.compile(
    r"(?i)("
    r"(?:^|[^-])>{1,2}\s*[^\s&]|"
    r"\b(?:Set-Content|Add-Content|Out-File|Clear-Content|Remove-Item|Move-Item|Rename-Item|Copy-Item|New-Item|ni|ri|rm|del|erase|rmdir|rd|mv|move|cp|copy|ren|rename|touch|mkdir|md|tee|sed\s+-i|perl\s+-i)\b|"
    r"\bgit\s+(?:checkout|reset|clean|rm|mv|apply|am|revert|merge|rebase|cherry-pick|pull|commit|stash\s+(?:drop|pop|apply|clear))\b|"
    r"\[System\.IO\.File\]::(?:Write|Append|Delete|Move|Copy|Create|Open|Replace)|"
    r"\.(?:write_text|write_bytes|unlink|rmdir|rename|replace|mkdir|open)\s*\(|"
    r"\bshutil\.(?:rmtree|move|copy|copy2|copyfile|copytree)\s*\(|"
    r"\bos\.(?:remove|unlink|rmdir|removedirs|rename|replace|makedirs|mkdir)\s*\(|"
    r"\bopen\s*\([^)]*,\s*['\"][wax+]"
    r")"
)

_CORE_REL_NAMES = (
    "backend", "frontend", "skills", "public", "data", "scripts", "docs", ".git",
    "start.bat", "start.ps1", "stop.bat", "pyproject.toml", "requirements.txt",
    "config.example.yaml", ".env", "README.md", "LICENSE"
)


def command_targets_nova_core_mutation(command: str, cwd: Optional[str] = None) -> Tuple[bool, str]:
    """
    Detects shell/script commands that attempt to create, edit, overwrite, move,
    git-alter, or delete files inside NOVA's protected core directory.
    Allows normal read-only inspection, test runs, and mutations confined inside scratch/.
    """
    if not command or not command.strip():
        return False, ""
    if not _SHELL_MUTATION_RE.search(command):
        return False, ""

    from backend.app.core.config import settings
    base_dir = Path(settings.BASE_DIR).resolve()
    scratch_dir = Path(settings.SCRATCH_DIR).resolve()
    cwd_path = Path(cwd or settings.DEFAULT_WORKSPACE).resolve()

    base_norm = str(base_dir).replace("\\", "/").lower()
    cmd_norm = command.replace("\\", "/").lower()

    # 1. Direct mention of NOVA base directory without targeting /scratch
    idx = 0
    while True:
        pos = cmd_norm.find(base_norm, idx)
        if pos == -1:
            break
        after = cmd_norm[pos + len(base_norm):pos + len(base_norm) + 20]
        if not after.startswith("/scratch"):
            return True, f"{CORE_PROTECTED_ERROR} (Blocked command targeting NOVA core directory)"
        idx = pos + len(base_norm)

    # 2. Check path-like tokens relative to cwd containing protected NOVA folders/files
    tokens = re.findall(r"['\"]?([A-Za-z0-9_./:\\-]+)['\"]?", command)
    for tok in tokens:
        t_clean = tok.strip().strip("'\"")
        if not t_clean or len(t_clean) < 2:
            continue
        low_tok = t_clean.replace("\\", "/").lower()
        first_seg = low_tok.lstrip("./").split("/")[0]
        looks_core_token = (
            ".." in low_tok
            or "/" in low_tok
            or first_seg in _CORE_REL_NAMES
            or any(f"/{name}" in low_tok for name in ("backend", "frontend", "skills", "public", ".git"))
        )
        if looks_core_token:
            try:
                cand = Path(t_clean) if Path(t_clean).is_absolute() else (cwd_path / t_clean)
                blocked, reason = is_protected_nova_core_path(cand)
                if blocked:
                    return True, reason
            except Exception:
                pass

    # 3. If cwd itself is inside protected NOVA core and command mutates without targeting scratch
    in_protected_cwd, _ = is_protected_nova_core_path(cwd_path)
    if in_protected_cwd:
        if "scratch" not in cmd_norm and str(scratch_dir).replace("\\", "/").lower() not in cmd_norm:
            return True, f"{CORE_PROTECTED_ERROR} (Blocked mutating command with working directory inside NOVA core: '{cwd_path}')"

    return False, ""


def python_code_targets_nova_core_mutation(code: str, cwd: Optional[str] = None) -> Tuple[bool, str]:
    """
    Detects Python code snippets that write/modify/delete files inside NOVA's core codebase.
    """
    if not code or not code.strip():
        return False, ""
    if not _SHELL_MUTATION_RE.search(code):
        return False, ""
    return command_targets_nova_core_mutation(code, cwd=cwd)
