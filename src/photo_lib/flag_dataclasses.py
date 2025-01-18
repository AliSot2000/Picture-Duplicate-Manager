from dataclasses import dataclass


@dataclass
class MainFlags:
    """
    Dataclass for flags in the main table
    """
    present: bool
    verify: bool
    trashed: bool
    org_google_metadata: bool
    sel_a: bool
    sel_b: bool

    @classmethod
    def from_int(cls, group: int):
        _present = bool(group & 0b1)
        _verify = bool(group & 0b10)
        _trashed = bool(group & 0b100)
        _org_google_metadata = bool(group & 0b1000)
        _sel_a = bool(group & 0b10000)
        _sel_b = bool(group & 0b100000)

        return cls(
            present=_present,
            verify=_verify,
            trashed=_trashed,
            org_google_metadata=_org_google_metadata,
            sel_a=_sel_a,
            sel_b=_sel_b,
        )

    def to_int(self):
        return (int(self.present)
                + int(self.verify) << 1
                + int(self.trashed) << 2
                + int(self.org_google_metadata) << 3
                + int(self.sel_a) << 4
                + int(self.sel_b) << 5)


@dataclass
class ReplacedFlags:
    """
    Dataclass for flags in the replaced table.
    """
    org_google_metadata: bool

    @classmethod
    def from_int(cls, group: int):
        _org_google_metadata = bool(group & 0b1)

        return cls(
            org_google_metadata=_org_google_metadata,
        )

    @classmethod
    def from_main_flags(cls, main_flags: MainFlags):
        return cls(org_google_metadata=main_flags.org_google_metadata)

    def to_int(self):
        return int(self.org_google_metadata)
