"""
Clustering and Duplicate Grouping Engine using Disjoint-Set, Quality Ranking,
and Memory-Bounded Candidate Generation.
"""

from typing import List, Dict, Set, Tuple, Optional, Any, Union
from collections import defaultdict
import os
import sys
import logging
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import itertools

from core.models import AudioTrack, DuplicateGroup, DuplicateType, FileAction, EvidenceReport, ScanCoverageReport
from core.comparator import compare_tracks
from core.config import DetectionConfig


def _compare_chunk_worker(
    pairs_or_item: Any,
    config: Optional[DetectionConfig] = None
) -> List[EvidenceReport]:
    if isinstance(pairs_or_item, tuple) and len(pairs_or_item) == 2 and isinstance(pairs_or_item[1], DetectionConfig):
        pairs, cfg = pairs_or_item
    else:
        pairs = pairs_or_item
        cfg = config or DetectionConfig()

    results = []
    for t_a, t_b in pairs:
        res = compare_tracks(t_a, t_b, config=cfg)
        if res.classification not in (DuplicateType.NO_MATCH, DuplicateType.UNCERTAIN):
            results.append(res)
    return results


class DisjointSet:
    """Disjoint-Set (Union-Find) with path compression and rank."""
    def __init__(self):
        self.parent = {}
        self.rank = {}

    def find(self, item: str) -> str:
        if item not in self.parent:
            self.parent[item] = item
            self.rank[item] = 0
            return item
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, a: str, b: str):
        root_a = self.find(a)
        root_b = self.find(b)
        if root_a != root_b:
            if self.rank[root_a] < self.rank[root_b]:
                self.parent[root_a] = root_b
            elif self.rank[root_a] > self.rank[root_b]:
                self.parent[root_b] = root_a
            else:
                self.parent[root_b] = root_a
                self.rank[root_a] += 1


class DuplicateGroupList(list):
    """Subclass of list that carries scan coverage metadata."""
    def __init__(self, items=None, coverage: Optional[ScanCoverageReport] = None):
        super().__init__(items or [])
        self.coverage = coverage or ScanCoverageReport()


def cluster_duplicates(
    tracks: List[AudioTrack], progress_callback=None, is_cancelled=None,
    config: Optional[DetectionConfig] = None, max_bucket_size: int = 500,
    max_pair_hits: int = 500_000, return_coverage: bool = False
) -> Union[List[DuplicateGroup], Tuple[List[DuplicateGroup], ScanCoverageReport]]:
    """Group candidates with bounded work and evidence to the retained copy.

    Exact identity is an equivalence relation; acoustic similarity is not.
    Only exact components may share proof transitively. Acoustic groups require
    a direct strong edge from the recommended retained component to every other
    component before automatic selection is allowed.
    """
    if max_bucket_size < 2 or max_pair_hits < 1:
        raise ValueError("Candidate limits must be positive (bucket size >= 2)")
    config = config or DetectionConfig()
    coverage = ScanCoverageReport()
    tracks = sorted(tracks, key=lambda t: t.filepath)
    ds, exact = DisjointSet(), DisjointSet()
    pair_results = {}

    def finish(items):
        coverage.is_complete = (coverage.scan_status != "CANCELLED" and
                                not coverage.is_approximate and not coverage.worker_failures)
        return (items, coverage) if return_coverage else DuplicateGroupList(items, coverage)

    def cancelled():
        if is_cancelled and is_cancelled():
            coverage.scan_status = "CANCELLED"
            return True
        return False

    def key(a, b):
        return tuple(sorted((a, b)))

    def link(a, b, kind):
        ds.union(a.filepath, b.filepath)
        exact.union(a.filepath, b.filepath)
        pair_results[key(a.filepath, b.filepath)] = EvidenceReport(
            a.filepath, b.filepath, kind, 100.0,
            is_exact_hash=kind == DuplicateType.EXACT_HASH,
            is_exact_audio=kind == DuplicateType.EXACT_AUDIO)

    sha_representatives = {}
    for track in tracks:
        if cancelled():
            return finish([])
        if track.sha256:
            representative = sha_representatives.setdefault(track.sha256, track)
            if representative is not track:
                link(representative, track, DuplicateType.EXACT_HASH)

    # Verify one representative per distinct binary identity, never all SHA pairs.
    pcm_groups = defaultdict(list)
    seen_exact = set()
    for track in tracks:
        component = exact.find(track.filepath)
        if track.audio_hash and component not in seen_exact:
            pcm_groups[track.audio_hash].append(track)
            seen_exact.add(component)
    from core.fingerprint import verify_full_normalized_pcm_match
    pcm_checks = 0
    for bucket in pcm_groups.values():
        representatives = []
        for track in bucket:
            if cancelled():
                return finish([])
            matched = False
            for rep in representatives:
                if cancelled():
                    return finish([])
                if abs(track.duration - rep.duration) > 0.5:
                    continue
                if pcm_checks >= max_pair_hits:
                    coverage.is_approximate = True
                    break
                pcm_checks += 1
                if verify_full_normalized_pcm_match(rep.filepath, track.filepath):
                    link(rep, track, DuplicateType.EXACT_AUDIO)
                    matched = True
                    break
            if not matched:
                representatives.append(track)

    # Index only exact representatives. Thousands of byte-identical copies add
    # linear storage and no redundant acoustic candidate pairs.
    component_track = {}
    for track in tracks:
        component_track.setdefault(exact.find(track.filepath), track)
    acoustic_tracks = sorted(component_track.values(), key=lambda t: t.filepath)
    shingle_index = defaultdict(list)
    for idx, track in enumerate(acoustic_tracks):
        if cancelled():
            return finish([])
        seen = set()
        for value in (track.fingerprint_raw or [])[:300]:
            if value:
                seen.update((value, value & 0xFFFFFFF0))
        for value in seen:
            shingle_index[value].append(idx)

    if progress_callback:
        progress_callback(0.0, 0, 0, "Filtrando coincidencias acústicas...")
    pair_hits = {}
    for shingle in sorted(shingle_index):
        if cancelled():
            return finish([])
        bucket = shingle_index[shingle]
        if len(bucket) > max_bucket_size:
            coverage.oversized_buckets += 1
            coverage.is_approximate = True
            coverage.candidate_pairs_dropped += (len(bucket) * (len(bucket)-1) -
                max_bucket_size * (max_bucket_size-1)) // 2
            bucket = bucket[:max_bucket_size]
        for a, b in itertools.combinations(bucket, 2):
            coverage.candidate_pairs_generated += 1
            pair = (a, b)
            if pair in pair_hits:
                pair_hits[pair] += 1
            elif len(pair_hits) < max_pair_hits:
                pair_hits[pair] = 1
            else:
                # Hard admission cap, independent of hit counts. Iteration is
                # deterministic; dropped counts are candidate occurrences.
                coverage.candidate_pairs_dropped += 1
                coverage.is_approximate = True
    candidates = sorted(pair for pair, hits in pair_hits.items() if hits >= 3)
    del pair_hits, shingle_index
    coverage.candidate_pairs_retained = len(candidates)
    total = len(candidates)
    if progress_callback:
        progress_callback(0.0, 0, total, f"Comparando huellas acústicas (0/{total:,})...")

    if total:
        workers = config.max_workers or max(1, min(6, (os.cpu_count() or 4) - 1))
        kwargs = {"max_workers": workers}
        if sys.version_info >= (3, 11):
            kwargs["max_tasks_per_child"] = 200
        iterator = iter(candidates)
        with ProcessPoolExecutor(**kwargs) as executor:
            pending = {}
            exhausted = False
            while pending or not exhausted:
                if cancelled():
                    for future in pending:
                        future.cancel()
                    break
                while not exhausted and len(pending) < workers * 2:
                    indices = list(itertools.islice(iterator, 50))
                    if not indices:
                        exhausted = True
                        break
                    chunk = [(acoustic_tracks[a], acoustic_tracks[b]) for a, b in indices]
                    try:
                        pending[executor.submit(_compare_chunk_worker, chunk, config)] = len(chunk)
                    except Exception:
                        coverage.worker_failures += 1
                        coverage.is_approximate = True
                        exhausted = True
                if not pending:
                    continue
                done, _ = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                for future in done:
                    chunk_size = pending.pop(future)
                    try:
                        for report in future.result():
                            ds.union(report.track_a_path, report.track_b_path)
                            pair_results[key(report.track_a_path, report.track_b_path)] = report
                    except Exception as exc:
                        coverage.worker_failures += 1
                        coverage.is_approximate = True
                        logging.getLogger(__name__).warning("Comparison chunk failed: %s", exc)
                    coverage.actual_comparisons += chunk_size
                    if progress_callback:
                        n = coverage.actual_comparisons
                        progress_callback(n / total, n, total, f"Comparando acústicamente ({n:,}/{total:,})...")
        if coverage.scan_status == "CANCELLED":
            return finish([])

    grouped = defaultdict(list)
    reports_by_group = defaultdict(list)
    direct_strong = set()
    strong = {DuplicateType.EXACT_HASH, DuplicateType.EXACT_AUDIO, DuplicateType.ACOUSTIC_DUPLICATE}
    for track in tracks:
        grouped[ds.find(track.filepath)].append(track)
    for report in pair_results.values():
        reports_by_group[ds.find(report.track_a_path)].append(report)
        if report.classification in strong and not report.requires_manual_review:
            direct_strong.add(key(exact.find(report.track_a_path), exact.find(report.track_b_path)))

    results = []
    for component, members in grouped.items():
        if cancelled():
            return finish([])
        if len(members) < 2:
            continue
        members.sort(key=lambda t: (-t.quality_score, -t.bitrate, -t.filesize, t.filepath))
        best = members[0]
        reports = reports_by_group[component]
        kinds = {r.classification for r in reports}
        kind = next(k for k in (DuplicateType.LOW_CONFIDENCE_REVIEW,
                    DuplicateType.POSSIBLE_DUPLICATE, DuplicateType.ACOUSTIC_DUPLICATE,
                    DuplicateType.EXACT_AUDIO, DuplicateType.EXACT_HASH) if k in kinds)
        review = any(r.requires_manual_review for r in reports) or kind in (
            DuplicateType.LOW_CONFIDENCE_REVIEW, DuplicateType.POSSIBLE_DUPLICATE)
        best_component = exact.find(best.filepath)
        verified_pairs = []
        for track in members[1:]:
            target_component = exact.find(track.filepath)
            if target_component == best_component or key(best_component, target_component) in direct_strong:
                verified_pairs.append([best.filepath, track.filepath])
            else:
                review = True
        reason = f"Mejor calidad detectada ({best.quality_score:.0f} pts)"
        if review and kind in strong:
            kind = DuplicateType.POSSIBLE_DUPLICATE
            reason += "; falta coincidencia directa con todas las copias: revisión requerida"
        for track in members:
            track.action = (FileAction.UNSET if review else
                            FileAction.KEEP if track is best else FileAction.DELETE)
        group = DuplicateGroup(
            group_id=f"group_{len(results)+1:03d}", primary_type=kind, tracks=members,
            best_track_path=best.filepath, best_track_reason=reason,
            average_similarity=min((r.confidence for r in reports), default=0.0),
            requires_manual_review=review, verified_pairs=verified_pairs)
        group.recalculate_space_saving()
        results.append(group)
    return finish(results)
