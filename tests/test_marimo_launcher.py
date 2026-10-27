from provenance_widget.marimo_launcher import DEFAULT_OMIT, split_omit


def test_omit_options_are_separated_from_marimo_arguments():
    rest, omit = split_omit(["run", "nb.py", "--omit", "a,b", "--headless", "--omit=c.d", "-p", "2718"])
    assert rest == ["run", "nb.py", "--headless", "-p", "2718"]
    assert omit == ["a", "b", "c.d"]


def test_no_omit_options_leaves_arguments_untouched():
    assert split_omit(["edit", "nb.py"]) == (["edit", "nb.py"], [])


def test_widget_plumbing_is_omitted_by_default():
    assert {"ProvenancePanel", "PmprovAdapter", "panel.snapshot", "snap.get"} <= set(DEFAULT_OMIT)
