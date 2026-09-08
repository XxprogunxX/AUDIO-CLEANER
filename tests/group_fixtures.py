"""Explicit pair evidence for synthetic file-operation fixtures.

These tests exercise journals and filesystem failures, not acoustic detection.
Real clustering and rejection of absent evidence are tested separately.
"""


def with_pair_evidence(group):
    group.verified_pairs = [
        [group.best_track_path, track.filepath] for track in group.tracks
        if track.filepath != group.best_track_path
    ]
    return group
