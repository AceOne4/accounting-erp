"""Role -> capability map. A user's role is per company (core.Membership).

Ported from the old project's Django groups:
- accountant: creates and edits drafts, cannot post
- reviewer: edits and posts, cannot create entries
- chief accountant: everything on the books, including accounts, deletes and posting
- system admin: read-only on the books, manages users
"""
from .models import Membership

R = Membership.Role

VIEW = {"account.view", "partner.view", "journal.view", "reports.view"}

ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    R.ACCOUNTANT: frozenset(
        VIEW | {"journal.create", "journal.edit", "partner.edit"}
    ),
    R.REVIEWER: frozenset(VIEW | {"journal.edit", "journal.post"}),
    R.CHIEF: frozenset(
        VIEW
        | {
            "journal.create",
            "journal.edit",
            "journal.post",
            "journal.delete",
            "account.manage",
            "partner.edit",
            "partner.delete",
        }
    ),
    R.ADMIN: frozenset(VIEW | {"users.manage"}),
}


def capabilities_for(role: str) -> frozenset[str]:
    return ROLE_CAPABILITIES.get(role, frozenset())
