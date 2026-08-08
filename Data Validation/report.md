# Dataset Validation 

I checked the results from the review agent + verifier (mohamed-branch) against my injection log to see if the "grounded" claims actually match the bugs I injected.

## What I found

First issue: the bug type names are different between my log and their output.
- My log uses: unused_variable, null_safety, off_by_one
- Their output uses: unused_variable, null_safety_violation, off_by_one_bound

Same bugs, just different names. I matched them manually.

## Results

Out of 107 claims marked "grounded" by the verifier:
- 98 actually match my injection log (same file, same bug type, line number close to what I logged)
- 6 are grounded but don't match the bug I actually injected (agent found something else)
- 3 are on files that aren't even in my injection log (2 of these are false positives on clean files, 1 is on a file outside the dataset)

So about 91.6% of the "grounded" claims are real matches to the actual injected bugs.

## Still empty

A lot of files are still returning zero comments:
- mutated (unused_variable): 23 out of 60 empty
- mutated_null: 23 out of 60 empty
- mutated_offbyone: 25 out of 60 empty

List of exact files is in empty_files.json.

## Clean files (false positives)

Out of 60 clean negative control files, 8 got flagged with a comment even though they don't have any injected bug. That's a false positive rate of about 13%.

## What I think should happen next

- Member 2 needs to check why so many files return empty comments
- Member 2 should also check why 1 comment showed up on a file from data/clean that's not even part of our dataset (looks like a scoping bug in the script)
- Once fixed, we should re-run and I'll re-check the numbers again before we put anything in the final results table

Files in this folder:
- report.md (this file)
- audit_details.json (raw mismatch data)
- empty_files.json (list of files with no comments)
