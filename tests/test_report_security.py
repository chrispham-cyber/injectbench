"""The /api/run endpoint hands an untrusted `id` straight to report.get_run,
so get_run must never read a file outside RESULTS_DIR. Found by an automated
security review in Milestone 2; these lock the fix in.
"""
from backend import report


def test_get_run_rejects_path_traversal():
    assert report.get_run("../../../../etc/passwd") is None
    assert report.get_run("../../secondlook/secret") is None


def test_get_run_rejects_unknown_id():
    assert report.get_run("definitely-not-a-real-run") is None
