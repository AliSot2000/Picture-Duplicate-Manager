from dataclasses import dataclass


# TODO Darktable?
@dataclass
class MainFlags:
    """
    Dataclass for flags in the main table
    """
    present: bool               # 1
    verify: bool                # 2
    trashed: bool               # 4
    org_google_metadata: bool   # 8
    sel_a: bool                 # 16
    sel_b: bool                 # 32
    has_thumbnail: bool         # 64
    has_miniature: bool         # 128
    duplicate: bool              # 256

    @classmethod
    def from_int(cls, group: int):
        _present = bool(group & 0b1)
        _verify = bool(group & 0b10)
        _trashed = bool(group & 0b100)
        _org_google_metadata = bool(group & 0b1000)
        _sel_a = bool(group & 0b1_0000)
        _sel_b = bool(group & 0b10_0000)
        _has_thumb = bool(group & 0b100_0000)
        _has_miniature = bool(group & 0b1000_0000)
        _duplicate = bool(group & 0b1_0000_0000)

        return cls(
            present=_present,
            verify=_verify,
            trashed=_trashed,
            org_google_metadata=_org_google_metadata,
            sel_a=_sel_a,
            sel_b=_sel_b,
            has_thumbnail=_has_thumb,
            has_miniature=_has_miniature,
            duplicate=_duplicate,
        )

    @classmethod
    def default(cls):
        """
        Create an instance with default values.
        """
        return cls(
            present=True,
            verify=False,
            trashed=False,
            org_google_metadata=True,  # INFO: No gm or gm present is equal to original
            sel_a=False,
            sel_b=False,
            has_thumbnail=False,
            has_miniature=False,
            duplicate=False,
        )

    def to_int(self):
        return (int(self.present)
                + int(self.verify) << 1
                + int(self.trashed) << 2
                + int(self.org_google_metadata) << 3
                + int(self.sel_a) << 4
                + int(self.sel_b) << 5
                + int(self.has_thumbnail) << 6
                + int(self.has_miniature) << 7
                + int(self.duplicate) << 8)


@dataclass
class GenericTableFlags:
    """
    Flags for generic tables.
    """
    stale: bool
    internal: bool

    @classmethod
    def from_int(cls, group: int):
        _stale = bool(group & 0b1)
        _internal = bool(group & 0b10)

        return cls(
            stale=_stale,
            internal=_internal,
        )

    def to_int(self):
        return (int(self.stale)
                + int(self.internal) << 1)