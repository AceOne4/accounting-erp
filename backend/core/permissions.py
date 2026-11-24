"""Role -> capability map. A user's role is per company (core.Membership).

Ported from the old project's Django groups:
- accountant: creates and edits drafts, cannot post
- reviewer: edits and posts, cannot create entries
- chief accountant: everything on the books, including accounts, deletes and posting
- system admin: read-only on the books, manages users
"""
from .models import Membership

R = Membership.Role

VIEW = {
    "account.view", "partner.view", "journal.view", "reports.view",
    "treasury.view", "inventory.view",
}

ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    R.ACCOUNTANT: frozenset(
        VIEW
        | {
            "journal.create", "journal.edit", "partner.edit",
            "treasury.voucher", "treasury.count", "inventory.count",
        }
    ),
    R.REVIEWER: frozenset(VIEW
        | {
            "journal.edit", "journal.post",
            "inventory.master", "inventory.receipt", "inventory.transfer",
        }),
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
            "treasury.voucher",
            "treasury.count",
            "inventory.master",
            "inventory.master_delete",
            "inventory.receipt",
            "inventory.receipt_delete",
            "inventory.transfer",
            "inventory.transfer_delete",
            "inventory.count",
            "inventory.override_lock",
        }
    ),
    R.ADMIN: frozenset(VIEW | {"users.manage"}),
}


def capabilities_for(role: str) -> frozenset[str]:
    return ROLE_CAPABILITIES.get(role, frozenset())
