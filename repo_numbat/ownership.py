"""Work out who owns a repository directory, portably.

On POSIX this is the directory's uid/gid compared with the current user and
their supplementary groups.  On Windows the owner SID of the directory is looked
up through the Win32 security API (ctypes, no extra packages) and compared with
the current user's token and group memberships.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Ownership:
    owner: str = "?"          # human-readable owner name
    group: str = ""           # POSIX group name (empty on Windows)
    is_mine: bool = False     # owned by the current user
    in_my_group: bool = False # group-owned by a group the user belongs to
    error: str = ""

    @classmethod
    def of(cls, path: Path) -> "Ownership":
        try:
            if sys.platform == "win32":
                return _windows_ownership(path)
            return _posix_ownership(path)
        except Exception as exc:  # pragma: no cover - platform specific
            return cls(error=str(exc))


def describe_ownership(o: Ownership) -> str:
    if o.error:
        return "unknown"
    if o.is_mine:
        return f"you ({o.owner})"
    if o.in_my_group:
        return f"your group ({o.group})" if o.group else f"your group ({o.owner})"
    if o.group:
        return f"{o.owner}:{o.group}"
    return o.owner


# ---------------------------------------------------------------------- POSIX
def _posix_ownership(path: Path) -> Ownership:
    import grp
    import pwd

    st = path.stat()
    try:
        owner = pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        owner = str(st.st_uid)
    try:
        group = grp.getgrgid(st.st_gid).gr_name
    except KeyError:
        group = str(st.st_gid)
    my_groups = set(os.getgroups()) | {os.getgid()}
    return Ownership(
        owner=owner,
        group=group,
        is_mine=st.st_uid == os.geteuid(),
        in_my_group=st.st_gid in my_groups,
    )


# -------------------------------------------------------------------- Windows
def _windows_ownership(path: Path) -> Ownership:  # pragma: no cover - Windows only
    import ctypes
    from ctypes import wintypes

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    OWNER_SECURITY_INFORMATION = 0x1
    SE_FILE_OBJECT = 1
    TOKEN_QUERY = 0x8
    TokenUser, TokenGroups = 1, 2

    # --- owner SID of the directory
    psid_owner = ctypes.c_void_p()
    psd = ctypes.c_void_p()
    advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
    rc = advapi32.GetNamedSecurityInfoW(
        str(path), SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION,
        ctypes.byref(psid_owner), None, None, None, ctypes.byref(psd),
    )
    if rc != 0:
        raise OSError(rc, "GetNamedSecurityInfoW failed")
    try:
        owner_name, owner_domain, owner_sid_str = _lookup_sid(advapi32, psid_owner)
        # --- current user's SID + group SIDs
        token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            user_sid = _token_sids(advapi32, token, TokenUser)[0]
            group_sids = _token_sids(advapi32, token, TokenGroups)
        finally:
            kernel32.CloseHandle(token)
    finally:
        kernel32.LocalFree(psd)

    label = f"{owner_domain}\\{owner_name}" if owner_domain else owner_name
    return Ownership(
        owner=label,
        is_mine=owner_sid_str == user_sid,
        in_my_group=owner_sid_str in group_sids,
    )


def _sid_to_string(advapi32, psid) -> str:  # pragma: no cover - Windows only
    import ctypes
    from ctypes import wintypes

    s = wintypes.LPWSTR()
    if not advapi32.ConvertSidToStringSidW(psid, ctypes.byref(s)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return s.value
    finally:
        ctypes.WinDLL("kernel32").LocalFree(s)


def _lookup_sid(advapi32, psid):  # pragma: no cover - Windows only
    import ctypes
    from ctypes import wintypes

    name_len, dom_len = wintypes.DWORD(0), wintypes.DWORD(0)
    use = wintypes.DWORD()
    advapi32.LookupAccountSidW(None, psid, None, ctypes.byref(name_len), None, ctypes.byref(dom_len), ctypes.byref(use))
    name = ctypes.create_unicode_buffer(max(name_len.value, 1))
    dom = ctypes.create_unicode_buffer(max(dom_len.value, 1))
    if not advapi32.LookupAccountSidW(None, psid, name, ctypes.byref(name_len), dom, ctypes.byref(dom_len), ctypes.byref(use)):
        return "?", "", _sid_to_string(advapi32, psid)
    return name.value, dom.value, _sid_to_string(advapi32, psid)


def _token_sids(advapi32, token, info_class) -> list[str]:  # pragma: no cover - Windows only
    import ctypes
    from ctypes import wintypes

    needed = wintypes.DWORD()
    advapi32.GetTokenInformation(token, info_class, None, 0, ctypes.byref(needed))
    buf = ctypes.create_string_buffer(needed.value)
    if not advapi32.GetTokenInformation(token, info_class, buf, needed, ctypes.byref(needed)):
        raise ctypes.WinError(ctypes.get_last_error())

    class SID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]

    if info_class == 1:  # TokenUser -> one SID_AND_ATTRIBUTES
        entry = SID_AND_ATTRIBUTES.from_buffer(buf)
        return [_sid_to_string(advapi32, entry.Sid)]
    count = ctypes.c_uint32.from_buffer(buf).value
    offset = ctypes.sizeof(ctypes.c_void_p)  # GroupCount padded to pointer size
    arr = (SID_AND_ATTRIBUTES * count).from_buffer(buf, offset)
    return [_sid_to_string(advapi32, e.Sid) for e in arr]
