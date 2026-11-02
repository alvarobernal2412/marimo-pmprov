import pytest

from provenance_widget.repeats import find_repeated_runs, describe_run


def keys(text: str):
    return list(text)  # one letter per step: the same letter is the same function with the same arguments


def test_four_steps_repeated_once_are_flagged_as_one_run():
    runs = find_repeated_runs(keys("abcdXabcd"), min_length=4)

    assert [(r.length, r.first, r.repeats) for r in runs] == [(4, 0, [5])]


def test_a_shorter_repeat_is_not_flagged():
    assert find_repeated_runs(keys("abcXabc"), min_length=4) == []


def test_the_same_step_later_in_a_different_context_is_not_a_repeat():
    # the step `a` runs again, but not as part of a repeated sequence
    assert find_repeated_runs(keys("abcdefa"), min_length=4) == []


def test_a_sequence_repeated_several_times_is_one_cluster():
    runs = find_repeated_runs(keys("abcdXabcdYabcd"), min_length=4)

    assert [(r.length, r.first, r.repeats) for r in runs] == [(4, 0, [5, 10])]


def test_two_different_sequences_are_two_clusters():
    runs = find_repeated_runs(keys("abcd1efgh2abcd3efgh"), min_length=4)

    assert sorted((r.first, r.repeats) for r in runs) == [(0, [10]), (5, [15])]


def test_a_repeat_is_not_counted_twice_inside_a_longer_one():
    runs = find_repeated_runs(keys("abcdefXabcdef"), min_length=4)

    assert [(r.length, r.first, r.repeats) for r in runs] == [(6, 0, [7])]


def test_a_run_never_overlaps_itself():
    # "aaaaaaaa" is a repeat of "aaaa", not of every shifted window
    runs = find_repeated_runs(keys("aaaaaaaa"), min_length=4)

    assert [(r.length, r.first, r.repeats) for r in runs] == [(4, 0, [4])]


def test_nothing_repeated_gives_nothing():
    assert find_repeated_runs(keys("abcdefgh"), min_length=4) == []
    assert find_repeated_runs([], min_length=4) == []


def test_the_minimum_length_is_a_choice():
    assert find_repeated_runs(keys("abXab"), min_length=2) != []
    with pytest.raises(ValueError):
        find_repeated_runs(keys("abab"), min_length=1)


def test_a_run_is_described_in_step_numbers_a_student_can_read():
    run = find_repeated_runs(keys("abcdXabcd"), min_length=4)[0]

    assert describe_run(run) == "Steps 6 to 9 repeat steps 1 to 4."
    clustered = find_repeated_runs(keys("abcdXabcdYabcd"), min_length=4)[0]
    assert describe_run(clustered) == "Steps 1 to 4 are repeated at steps 6 to 9 and 11 to 14."
