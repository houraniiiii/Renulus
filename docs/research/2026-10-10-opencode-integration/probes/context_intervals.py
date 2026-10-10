"""Research-only interval simulation; does not execute OpenCode or a model.

Independently models the merge-order claim in the user's referenced UniiChat
article, pinned in parent-context.md. No patient or application profile data.
"""
import json


def reference_push(states, item):
    carry = item
    for index, (start, bit) in enumerate(states):
        if bit == 0:
            states[index] = (start, 1)
            return
        states[index] = (carry, 0)
        carry = start
    states.append((carry, 0))


def intervals(states, count):
    starts = sorted(start for start, _ in states)
    return [(start, end - start) for start, end in zip(starts, starts[1:] + [count])]


def merge_to(view, count, budget, use_last=True, ready=lambda _: True):
    while len(view) > budget:
        candidates = []
        for index in range(len(view) - 1):
            start, size = view[index]
            other, width = view[index + 1]
            if width != size or other != start + size or start % (2 * size):
                continue
            parent = (start, 2 * size)
            if not ready(parent):
                continue
            anchor = start + 2 * size - 1 if use_last else start
            candidates.append(((count - anchor) / size, -start, index, parent))
        if not candidates:
            break
        _, _, index, parent = max(candidates)
        view[index:index + 2] = [parent]
    return view


def verify_partition(view, count):
    cursor = 0
    for start, size in view:
        assert start == cursor and size > 0 and size & (size - 1) == 0
        assert start % size == 0
        cursor += size
    assert cursor == count


def main():
    states, correct, wrong = [], [], []
    correct_matches = wrong_matches = 0
    for count in range(1, 20_002):
        reference_push(states, count - 1)
        expected = intervals(states, count)
        correct.append((count - 1, 1))
        wrong.append((count - 1, 1))
        merge_to(correct, count, len(expected))
        merge_to(wrong, count, len(expected), use_last=False)
        verify_partition(correct, count)
        verify_partition(wrong, count)
        correct_matches += correct == expected
        wrong_matches += wrong == expected
    assert correct_matches == 20_001
    assert wrong_matches < correct_matches

    # A non-ready parent must not cause loss of its two children.
    delayed = [(0, 1), (1, 1)]
    assert merge_to(delayed, 2, 1, ready=lambda _: False) == [(0, 1), (1, 1)]

    # Persisting a view preserves its exact ordering; reconstructing a new
    # budgeted view is not asserted to reproduce a historic batching schedule.
    encoded = json.dumps(correct, separators=(",", ":")).encode("utf-8")
    reopened = [tuple(pair) for pair in json.loads(encoded)]
    assert reopened == correct
    verify_partition(reopened, 20_001)

    # Byte length and character length are different even before tokenization.
    samples = ["a" * 512, "é" * 512, "腎" * 512]
    sizes = [len(text.encode("utf-8")) for text in samples]
    assert sizes == [512, 1024, 1536]
    print(json.dumps({
        "scope": "research-only mathematical simulation, no model/runtime",
        "steps": 20_001,
        "last_message_age_matches": correct_matches,
        "first_message_age_matches": wrong_matches,
        "partition_checks": 40_003,
        "unready_parent_keeps_children": True,
        "view_json_round_trip": True,
        "utf8_bytes_for_512_characters": sizes,
        "not_tested": ["summary recall", "provider cache", "token windows", "OpenCode execution"],
    }, indent=2))


if __name__ == "__main__":
    main()
